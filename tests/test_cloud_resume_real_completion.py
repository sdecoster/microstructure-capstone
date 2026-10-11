"""Resume gates exercised against a real downloaded cloud completion record."""
from dataclasses import asdict
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'investigation'))
from cloud_parallel_plan import Source
from cloud_resume import validated_completion

@pytest.fixture
def real_record():
    path = ROOT / 'data/recovery-sample-completion.json'
    if not path.exists():
        pytest.skip('real cloud completion cache unavailable')
    return json.loads(path.read_text(encoding='utf-8-sig'))

class Bucket:
    def __init__(self, record):
        self.record = record
        self.remote = [SimpleNamespace(name=f['name'], size=f['bytes'], md5_hash=f['md5_hash']) for f in record['files']]
    def blob(self, name):
        return SimpleNamespace(download_as_text=lambda: json.dumps(self.record))
    def list_blobs(self, prefix):
        return self.remote

def test_real_completion_accepts_matching_listing_and_rejects_corruption(real_record):
    bucket = Bucket(real_record)
    source = Source(**real_record['source'])
    assert validated_completion(bucket, 'ordinary-v1-20260927', source)
    bucket.remote[0].md5_hash = 'changed-checksum'
    assert not validated_completion(bucket, 'ordinary-v1-20260927', source)

def test_real_completion_rejects_missing_remote_part(real_record):
    bucket = Bucket(real_record)
    bucket.remote.pop()
    assert not validated_completion(bucket, 'ordinary-v1-20260927', Source(**real_record['source']))

def test_real_completion_rejects_wrong_source_size(real_record):
    bucket = Bucket(real_record)
    source = Source(**dict(real_record['source'], size_bytes=real_record['source']['size_bytes'] + 1))
    assert not validated_completion(bucket, 'ordinary-v1-20260927', source)

def _native_cancel_child(stop, ready, result):
    import signal
    import cloud_resume
    from cloud_convert import should_stop
    cloud_resume.initialize_worker(stop)
    ready.set()
    observed = stop.wait(10)
    result.put((observed and should_stop(cloud_resume._worker_stop), signal.getsignal(signal.SIGTERM) == signal.SIG_IGN))

def test_spawned_worker_observes_native_cancel_without_manager_rpc():
    import multiprocessing
    context = multiprocessing.get_context('spawn')
    stop, ready, result = context.Event(), context.Event(), context.Queue()
    process = context.Process(target=_native_cancel_child, args=(stop, ready, result))
    process.start()
    try:
        assert ready.wait(10)
        stop.set()
        assert result.get(timeout=10) == (True, True)
        process.join(10)
        assert process.exitcode == 0
    finally:
        stop.set()
        process.join(2)
        if process.is_alive():
            process.kill()
            process.join(2)
        result.close()
