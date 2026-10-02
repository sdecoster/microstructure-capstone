"""Validate a bounded cloud pilot's manifests, uploaded Parquet, and dimensions.

Downloads compact pilot output only, never raw sources. Refuses large/unbounded
runs. No cloud writes; emit an aggregate JSON report to stdout.
"""
from __future__ import annotations

import argparse
from collections import Counter
import io
import json

from google.cloud import storage
import pyarrow as pa
import pyarrow.parquet as pq

from cloud_convert import SCALE, VERSION, key


def validate(bucket, run, expected_sources):
    manifests = list(bucket.list_blobs(prefix=f'runs/{run}/completions/', max_results=5))
    if len(manifests) != expected_sources or not 1 <= expected_sources <= 4:
        raise ValueError('pilot must have exactly the expected one to four completions')
    records = [json.loads(blob.download_as_text()) for blob in manifests]
    declared_bytes = sum(f['bytes'] for record in records for f in record['files'])
    if declared_bytes > 1024**3:
        raise ValueError('compact pilot validation is capped at 1 GiB')
    summaries = []
    for record in records:
        assert record['version'] == VERSION and record['numeric_scale'] == SCALE
        source_id = key(record['source']['uri'])
        assert record['source_id'] == source_id
        stats = record['stats']
        assert stats['unique_payloads'] == sum(value for name, value in stats.items() if name.startswith('event:'))
        assert stats['outer_messages'] == sum(stats.get(name, 0) for name in ('unique_payloads', 'duplicates_skipped', 'invalid_content', 'non_feed_envelopes'))
        declared_rows = record['fact_rows']
        for table, event in [('book_headers', 'book'), ('trades', 'last_trade_price'), ('tick_size_changes', 'tick_size_change')]:
            assert declared_rows.get(table, 0) == stats.get('event:' + event, 0)
        assert not declared_rows.get('key_collisions', 0)
        prefix = f'runs/{run}/data/attempt={record["attempt_id"]}/'
        remote = {blob.name: blob for blob in bucket.list_blobs(prefix=prefix)}
        assert len(remote) == len(record['files'])
        actual_rows = Counter()
        dimensions = {'markets': {}, 'assets': {}}
        samples = {}
        for file in record['files']:
            blob = remote[file['name']]
            assert blob.size == file['bytes'] and blob.md5_hash == file['md5_hash']
            table_name = file['name'].split('/table=', 1)[1].split('/', 1)[0]
            # The storage client verifies the transport checksum; Arrow also
            # reads every file so corrupt Parquet cannot pass a size-only check.
            table = pq.ParquetFile(io.BytesIO(blob.download_as_bytes())).read()
            actual_rows[table_name] += table.num_rows
            for name in ('price_i', 'size_i', 'old_tick_size_i', 'new_tick_size_i'):
                if name in table.column_names:
                    assert pa.types.is_integer(table.schema.field(name).type)
                    assert table[name].null_count == 0
            if table_name in dimensions:
                key_name, id_name = ('market_key', 'market_id') if table_name == 'markets' else ('asset_key', 'asset_id')
                for row in table.select([key_name, id_name]).to_pylist():
                    assert row[key_name] == key(row[id_name])
                    assert row[key_name] not in dimensions[table_name]
                    dimensions[table_name][row[key_name]] = row[id_name]
            elif table_name not in samples:
                samples[table_name] = table.slice(0, 8).to_pylist()
        assert dict(actual_rows) == declared_rows
        for table_rows in samples.values():
            for row in table_rows:
                for dimension, key_name, id_name in [('markets', 'market_key', 'market_id'), ('assets', 'asset_key', 'asset_id')]:
                    if row.get(key_name):
                        assert dimensions[dimension][row[key_name]] == row[id_name]
        summaries.append(dict(source=record['source']['uri'], input_bytes=record['source']['size_bytes'],
                              files=len(remote), parquet_bytes=sum(blob.size for blob in remote.values()),
                              stats=stats, rows=dict(actual_rows), status='validated'))
    return dict(run_id=run, sources=summaries, total_input_bytes=sum(x['input_bytes'] for x in summaries),
                total_parquet_bytes=declared_bytes,
                validation='all output files decoded; checksums/sizes/row counts/accounting/exact dimension keys; sample fact-dimension references')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compact-bucket', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--expected-sources', type=int, default=2)
    args = parser.parse_args()
    print(json.dumps(validate(storage.Client().bucket(args.compact_bucket), args.run_id, args.expected_sources), sort_keys=True))


if __name__ == '__main__':
    main()
