"""Bounded, offline comparison of the actual converter on cached real feeds.

No network or cloud writes. Parquet is temporary; only aggregate timings/hashes
are saved. Compare shutdown RPC frequency separately from existing optimizations.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import hashlib
import io
import json
from multiprocessing import Manager
from pathlib import Path
import subprocess
import tempfile
import time
import types

import pyarrow.parquet  # Import outside the timed loop.
import zstandard
import cloud_convert as current

ROOT = Path(__file__).resolve().parents[1]
OLD = None


def initialize():
    global OLD
    code = subprocess.check_output(
        ['git', 'show', '2fc8898:investigation/cloud_convert.py'], cwd=ROOT
    ).decode('utf-8-sig')
    OLD = types.ModuleType('deployed_converter')
    exec(compile(code, 'deployed_converter', 'exec'), OLD.__dict__)


def warm(_):
    return True


def benchmark(task):
    path, mode, cap, stop = task
    module = OLD if mode.startswith('deployed') else current
    interval = 1 if mode == 'deployed_every_record' else 1024
    module.key.cache_clear() if hasattr(module.key, 'cache_clear') else None
    if hasattr(module, '_scale_text'):
        module._scale_text.cache_clear()
    stats = Counter()
    dims = {'markets': {}, 'assets': {}}
    seen = set()
    with tempfile.TemporaryDirectory(prefix='poly-offline-audit-') as temp:
        root = Path(temp)
        writer = module.Writer(root, 'audit', 'real-cached-source', 50000)
        started = time.perf_counter()
        with Path(path).open('rb') as raw:
            with zstandard.ZstdDecompressor().stream_reader(raw) as decoder:
                for ordinal, line in enumerate(io.TextIOWrapper(decoder, encoding='utf8', errors='replace'), 1):
                    if ordinal > cap:
                        break
                    if ordinal % interval == 0:
                        stats['stop_rpc_calls'] += 1
                        if stop.is_set():
                            raise RuntimeError('unexpected audit cancellation')
                    if not line.strip():
                        continue
                    stats['outer_messages'] += 1
                    try:
                        envelope = module.loads(line) if hasattr(module, 'loads') else json.loads(line)
                    except json.JSONDecodeError:
                        writer.add('non_feed_envelopes', dict(source_id='real-cached-source', source_ordinal=ordinal, reason='invalid_json'))
                        continue
                    if envelope.get('message_type') != 'feed_message':
                        stats['non_feed_envelopes'] += 1
                        writer.add('non_feed_envelopes', dict(source_id='real-cached-source', source_ordinal=ordinal, message_type=envelope.get('message_type'), reason='non_feed'))
                        continue
                    payload = envelope.get('content')
                    early_fp = None
                    if mode == 'current_early_dedupe':
                        content, early_fp = current.decode_feed(payload, seen)
                        if early_fp in seen:
                            stats['duplicates_skipped'] += 1
                            continue
                    else:
                        content = module.content(payload)
                    if content is None:
                        stats['invalid_content'] += 1
                        writer.add('invalid_content', dict(source_id='real-cached-source', source_ordinal=ordinal, reason='not_object'))
                        continue
                    if mode.startswith('deployed'):
                        fp = hashlib.blake2b(json.dumps(content, sort_keys=True, separators=(',', ':')).encode(), digest_size=16).digest()
                    else:
                        fp = early_fp if early_fp is not None else current.fingerprint(payload, content)
                    if fp in seen:
                        stats['duplicates_skipped'] += 1
                        continue
                    seen.add(fp)
                    stats['unique_payloads'] += 1
                    stats['event:' + str(content.get('event_type'))] += 1
                    market = content.get('market')
                    if isinstance(market, (str, int)):
                        dims['markets'].setdefault(module.key(market), str(market))
                    for table, row in module.rows(content, 'real-cached-source', ordinal):
                        writer.add(table, row)
                        if row.get('asset_key'):
                            dims['assets'].setdefault(row['asset_key'], row['asset_id'])
        for table, values in dims.items():
            key_column, id_column = ('market_key', 'market_id') if table == 'markets' else ('asset_key', 'asset_id')
            for k, value in values.items():
                writer.add(table, dict(source_id='real-cached-source', **{key_column: k, id_column: value}))
        writer.close()
        seconds = time.perf_counter() - started
        digest = hashlib.sha256()
        output_bytes = 0
        files = sorted(root.rglob('*.parquet'))
        for part in files:
            digest.update(part.relative_to(root).as_posix().encode())
            encoded = part.read_bytes()
            output_bytes += len(encoded)
            digest.update(encoded)
        return dict(source=str(Path(path).relative_to(ROOT)), mode=mode, seconds=seconds,
                    rows=dict(writer.count), stats=dict(stats), files=len(files),
                    parquet_bytes=output_bytes, output_sha256=digest.hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cap', type=int, default=50000)
    parser.add_argument('--processes', type=int, default=4)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.cap <= 100000 or not 1 <= args.processes <= 4:
        raise ValueError('audit is capped at 100000 messages per task and four processes')
    paths = [ROOT / 'data/market_filter_investigation/raw' / date / hour
             for date, hour in [('2026-05-25', '0800.jsonl.zst.prefix-67108864'),
                                ('2026-08-14', '0900.jsonl.zst.prefix-67108864')]]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    report = {'scope': 'offline cached real prefixes; excludes GCS; timings are local Windows, not a cloud ETA',
              'cap_per_task': args.cap, 'processes': args.processes,
              'orjson_version': None if current.orjson is None else current.orjson.__version__, 'runs': []}
    references = {}
    with Manager() as manager:
        stop = manager.Event()
        with ProcessPoolExecutor(max_workers=args.processes, initializer=initialize) as pool:
            list(pool.map(warm, range(args.processes)))
            # Repeat after all modes have warmed the interpreter/Arrow caches.
            for mode in ['deployed_every_record', 'deployed_batched_poll', 'current_batched_poll', 'current_early_dedupe'] * 2:
                started = time.perf_counter()
                tasks = [(str(paths[i % len(paths)]), mode, args.cap, stop) for i in range(args.processes)]
                measurements = list(pool.map(benchmark, tasks))
                elapsed = time.perf_counter() - started
                for measurement in measurements:
                    source = measurement['source']
                    if mode == 'deployed_every_record':
                        references[source] = measurement['output_sha256']
                    measurement['output_matches_deployed'] = references[source] == measurement['output_sha256']
                    if not measurement['output_matches_deployed']:
                        raise AssertionError('Parquet content differs from deployed code: ' + source)
                report['runs'].append(dict(cycle=len(report['runs'])//4+1,mode=mode, aggregate_wall_seconds=elapsed, measurements=measurements))
                print(json.dumps(report['runs'][-1]), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
