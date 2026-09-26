poly-raw R2 Data Share
======================

Contents
--------
- Requested three-month window: May 16, 2026 through August 16, 2026.
- Actual object date range: May 23, 2026 through August 16, 2026. No objects
  were available for May 16 through May 22.
- August 16, 2026 was the latest object date in the bucket when this snapshot
  was generated.
- This is a point-in-time snapshot. Objects uploaded after the snapshot was
  generated are not included.
- Includes the main raw dataset, raw/onchain, raw/external, and raw/_index.
- Runtime state files under state/ are not included.
- Total: 6,590 objects and approximately 2.740 TiB.

Expiration
----------
- The signed download URLs in manifest.tsv are valid for seven days from
  generation.
- Start and complete the download before September 28, 2026 at 13:17
  (Asia/Shanghai, UTC+8).

How to Download
---------------
1. Extract this ZIP archive.
2. Make sure the destination disk has at least 2.8 TiB of free space.
3. From the extracted directory, run:

   python3 download.py --output /path/to/destination --jobs 8

The downloader supports concurrent transfers, retries, and resuming partial
downloads. If it is interrupted, run the same command again to continue.
If the network or disk is under heavy load, reduce --jobs from 8 to 4.

Manifest Format
---------------
manifest.tsv contains one object per line in the following format:

  size_in_bytes<TAB>object_path<TAB>temporary_signed_url
