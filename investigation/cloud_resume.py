"""Resume existing disjoint assignments with bounded shutdown and no Manager RPCs."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import asdict
import json
import multiprocessing
from pathlib import Path
import signal
from cloud_convert import VERSION, SCALE, cname, convert, key, parse_worker_indices, selected_work
from cloud_parallel_plan import Source

_worker_stop = None


def initialize_worker(stop):
    global _worker_stop
    _worker_stop = stop
    # Only the supervisor handles group shutdown. It sets the shared native Event
    # outside its signal handler, avoiding reentrant locks and Manager deadlocks.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)


def validated_completion(bucket, run, source):
    from google.api_core.exceptions import NotFound
    try:
        record = json.loads(bucket.blob(cname(run, key(source.uri))).download_as_text())
    except NotFound:
        return False
    except (ValueError, TypeError):
        return False
    if (record.get('version') != VERSION or record.get('numeric_scale') != SCALE
            or record.get('source') != asdict(source) or not record.get('files')
            or record.get('source_id') != key(source.uri) or not record.get('attempt_id')):
        return False
    prefix = f'runs/{run}/data/attempt={record["attempt_id"]}/'
    files = record['files']
    if (any(not f.get('name', '').startswith(prefix) or not f.get('md5_hash') for f in files)
            or len({f['name'] for f in files}) != len(files)):
        return False
    # Paginated metadata listing validates all files without an RPC per file.
    remote = {blob.name: blob for blob in bucket.list_blobs(prefix=prefix)}
    return (len(remote) == len(files) and all(
        f['name'] in remote and remote[f['name']].size == f['bytes']
        and remote[f['name']].md5_hash == f['md5_hash'] for f in files))


def run_assignment(plan, index, raw, compact, run, stage_root, validate_only=False, max_sources=None):
    from google.cloud import storage
    bucket = storage.Client().bucket(compact)
    work = selected_work(plan, [index], max_sources)
    summary = dict(worker_index=index, assigned=len(work), validated=0, converted=0, input_bytes=0)
    for source in work:
        if _worker_stop is not None and _worker_stop.is_set():
            return dict(summary, status='stopped')
        if validated_completion(bucket, run, source):
            summary['validated'] += 1
        elif validate_only:
            raise RuntimeError(f'Completion failed validation: {source.uri}')
        else:
            result = convert(source, raw, compact, run, stage_root, stop=_worker_stop)
            if result['status'] == 'stopped':
                return dict(summary, status='stopped')
            # Include checksums in the acceptance gate for new output too.
            if not validated_completion(bucket, run, source):
                raise RuntimeError(f'New output failed metadata validation: {source.uri}')
            summary['converted'] += 1
            print(json.dumps(dict(phase='source_completed', **result, worker_index=index)), flush=True)
        summary['input_bytes'] += source.size_bytes
        print(json.dumps(dict(phase='assignment_progress', **summary)), flush=True)
    return dict(summary, status='completed')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-bucket', required=True)
    p.add_argument('--compact-bucket', required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--plan-object', required=True)
    p.add_argument('--worker-indices', required=True)
    p.add_argument('--staging-root', default='/tmp/poly-archive')
    p.add_argument('--validate-only', action='store_true')
    p.add_argument('--max-sources', type=int)
    a = p.parse_args()
    if a.max_sources is not None and a.max_sources < 1:
        p.error('--max-sources must be positive')
    from google.cloud import storage
    # Read only: never create or replace the immutable plan.
    plan = json.loads(storage.Client().bucket(a.compact_bucket).blob(a.plan_object).download_as_text())
    indices = parse_worker_indices(a.worker_indices, len(plan['workers']))
    if not indices:
        p.error('explicit worker indices required')
    work = selected_work(plan, indices)
    if len({s.uri for s in work}) != len(work):
        raise ValueError('selected assignments overlap')
    Path(a.staging_root).mkdir(parents=True, exist_ok=True)
    requested = False
    def request_stop(signum, frame):
        nonlocal requested
        requested = True
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    context = multiprocessing.get_context('spawn')
    stop = context.Event()
    failures = []
    with ProcessPoolExecutor(max_workers=len(indices), mp_context=context,
                             initializer=initialize_worker, initargs=(stop,)) as pool:
        pending = {pool.submit(run_assignment, plan, index, a.raw_bucket, a.compact_bucket,
                               a.run_id, a.staging_root, a.validate_only, a.max_sources)
                   for index in indices}
        while pending:
            if requested:
                stop.set()
            done, pending = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
            for future in done:
                try:
                    result = future.result()
                    print(json.dumps(dict(phase='assignment_finished', **result)), flush=True)
                    if result['status'] != 'completed':
                        failures.append(result)
                        stop.set()
                except Exception as error:
                    failures.append(str(error))
                    stop.set()
                    print(json.dumps(dict(phase='failure', error=str(error))), flush=True)
    if failures or requested:
        raise SystemExit(1)
    print(json.dumps(dict(phase='recovery_completed', worker_indices=indices)), flush=True)


if __name__ == '__main__':
    main()
