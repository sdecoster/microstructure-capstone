# Raw archive preservation setup

This setup preserves supplied compressed source files before processing. It does
not begin a full transfer until the pilot completes and is reviewed.

## Bucket settings

Create one raw staging bucket in `us-central1`:

- Regional location; Standard storage class.
- Public access prevention enforced and uniform bucket-level access enabled.
- Object versioning off; no retention lock and no automatic deletion rule.
- Keep the default soft-delete recovery setting during the pilot. Before deleting
  the full raw archive, explicitly account for its recovery-period storage cost.

Do not upload raw data manually. Do not make the bucket or URL-list public.

## Private transfer plan

Run from the repository root. These commands only create ignored local planning
files and never start a cloud job.

```powershell
py investigation/cloud_archive_transfer.py pilot
py investigation/cloud_archive_transfer.py audit
```

The generated `data/cloud_archive_transfer/urls.tsv` contains signed URLs. Never
commit, email, print, or publish it. `inventory.csv` has no URLs and maps source
paths to the object names Storage Transfer Service will produce.

## Cloud pilot

1. Upload only `urls.tsv` to a private `control/` prefix in the raw bucket.
2. Enable Storage Transfer Service in the project.
3. Grant its Google-managed service agent read access to `control/urls.tsv` and
   write access to the raw bucket. Do not create a service-account key.
4. Create a URL-list transfer to `gs://RAW_BUCKET/preserved/`, select Standard
   storage, `never` overwrite, no deletion options, and explicit Run once.
5. Run the pilot and confirm its object count and byte total against
   `inventory.csv`. Destination names are prefixed by the source hostname and
   path; that is expected for URL-list transfers.

Only after reconciliation should a full one-time job be created from a freshly
generated full URL list. It must use the same no-delete and never-overwrite
settings, and its progress must be watched in the Transfer Service operation log.
