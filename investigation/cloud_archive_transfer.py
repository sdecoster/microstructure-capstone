'''Prepare and audit bounded Google Cloud Storage Transfer Service URL lists.

The share manifest contains signed source URLs. URL lists produced by this
module belong under the ignored data/ directory and must never be committed,
uploaded to a public location, or printed to a terminal.

This tool only prepares local files and audits inventory. It never calls Google
Cloud, creates a transfer job, or downloads source data.
'''
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'poly-data-share/poly-data-share/manifest.tsv'
PRIVATE_DIR = ROOT / 'data/cloud_archive_transfer'


@dataclass(frozen=True)
class SourceObject:
    size: int
    source_path: str
    url: str

    @property
    def destination_object(self) -> str:
        parts = urlsplit(self.url)
        return '/'.join((parts.netloc, parts.path.lstrip('/')))


def read_manifest(path: Path = MANIFEST) -> list[SourceObject]:
    rows: list[SourceObject] = []
    with path.open(encoding='utf-8', newline='') as handle:
        for line_number, row in enumerate(csv.reader(handle, delimiter='\t'), 1):
            if len(row) != 3:
                raise ValueError('Manifest row {} has {} fields, expected 3'.format(line_number, len(row)))
            size_text, source_path, url = row
            size = int(size_text)
            if size < 0 or not source_path or not url.startswith(('https://', 'http://')):
                raise ValueError('Invalid manifest row {}'.format(line_number))
            rows.append(SourceObject(size, source_path, url))
    if not rows:
        raise ValueError('Manifest is empty')
    if len({row.source_path for row in rows}) != len(rows):
        raise ValueError('Manifest has duplicate source paths')
    if len({row.destination_object for row in rows}) != len(rows):
        raise ValueError('Destination mapping has collisions')
    return rows


def choose_pilot(rows: list[SourceObject], max_objects: int = 3, max_bytes: int = 75_000_000) -> list[SourceObject]:
    '''Select real small source objects across archive areas, under a hard cap.'''
    if max_objects < 1 or max_bytes < 1:
        raise ValueError('Pilot caps must be positive')
    prefixes = ('raw/', 'raw/_index/', 'raw/external/', 'raw/onchain/')
    selected: list[SourceObject] = []
    used = 0
    for prefix in prefixes:
        candidates = sorted((row for row in rows if row.source_path.startswith(prefix)), key=lambda row: (row.size, row.source_path))
        for row in candidates:
            if len(selected) >= max_objects:
                break
            if used + row.size <= max_bytes:
                selected.append(row)
                used += row.size
                break
    if not selected:
        raise ValueError('No manifest objects fit the pilot cap')
    return selected


def write_plan(rows: list[SourceObject], tsv_path: Path, inventory_path: Path) -> dict[str, int]:
    tsv_path.parent.mkdir(parents=True, exist_ok=True)
    with tsv_path.open('w', encoding='utf-8', newline='') as handle:
        handle.write('TsvHttpData-1.0\n')
        for row in rows:
            handle.write('{}\t{}\n'.format(row.url, row.size))
    with inventory_path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=('source_path', 'destination_object', 'size_bytes'))
        writer.writeheader()
        for row in rows:
            writer.writerow({'source_path': row.source_path, 'destination_object': row.destination_object, 'size_bytes': row.size})
    return {'objects': len(rows), 'bytes': sum(row.size for row in rows)}


def audit_inventory(inventory_path: Path) -> dict[str, int]:
    with inventory_path.open(encoding='utf-8', newline='') as handle:
        rows = list(csv.DictReader(handle))
    required = {'source_path', 'destination_object', 'size_bytes'}
    if not rows or set(rows[0]) != required:
        raise ValueError('Inventory has unexpected columns')
    return {'objects': len(rows), 'bytes': sum(int(row['size_bytes']) for row in rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description='Prepare a private URL-list transfer plan without starting a transfer.')
    parser.add_argument('command', choices=('pilot', 'full', 'audit'))
    parser.add_argument('--output-dir', type=Path, default=PRIVATE_DIR)
    parser.add_argument('--max-objects', type=int, default=3)
    parser.add_argument('--max-bytes', type=int, default=75_000_000)
    args = parser.parse_args()
    if args.command == 'audit':
        print(json.dumps(audit_inventory(args.output_dir / 'inventory.csv'), sort_keys=True))
        return
    rows = read_manifest()
    selected = choose_pilot(rows, args.max_objects, args.max_bytes) if args.command == 'pilot' else rows
    summary = write_plan(selected, args.output_dir / 'urls.tsv', args.output_dir / 'inventory.csv')
    summary['kind'] = args.command
    summary['url_list'] = str((args.output_dir / 'urls.tsv').relative_to(ROOT))
    summary['inventory'] = str((args.output_dir / 'inventory.csv').relative_to(ROOT))
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()
