# Remaining ordinary archive recovery - October 10, 2026

The original worker 2 stopped logging after an October 3 SIGTERM request. The coordinator/manager/remaining child were blocked. It was stopped through Compute Engine before recovery, so its old assignment processes cannot overlap the replacement.

## Recovery layout

Use poly-archive-worker-1 (e2-standard-8, 32 GiB RAM) with two spawned processes for the existing plan's worker indices 4,5. Preserve run ordinary-v1-20260927 and immutable plan runs/ordinary-v1-20260927/plan-6-workers-reverse-20261001.json. Indices 0-3 are finished. No raw objects, completed outputs or existing plan are deleted or rewritten by setup.

investigation/cloud_resume.py reads the existing plan only. Each process handles its assignment sequentially, validates completed source metadata by paginated listing (source/version/scale, all object sizes and MD5s), skips validated completions, and uses the existing lossless converter for missing/invalid completions. The new output is validated again before acceptance. No cross-source deduplication or physical schema change is introduced.

Use spawn plus a native shared Event. Child processes ignore SIGINT/SIGTERM; the supervisor records the request in its signal handler, then sets the native Event outside that handler. This avoids the old Manager RPC/reentrant signal path. The exact cause of the old shutdown deadlock is not established.

## Automatic stopping and spending limits

- tools/poly-archive-recovery.service: shutdown the guest on completion, failure, OOM, or service timeout; no automatic job restart.
- systemd RuntimeMaxSec=72h, TimeoutStopSec=120, KillMode=mixed. SIGTERM goes to the supervisor, followed by group SIGKILL if cleanup hangs.
- MemoryHigh=24G and MemoryMax=26G on the 32 GiB VM; two conversion processes.
- Independently set Compute Engine scheduling terminationTime to 72 hours after setup, instanceTerminationAction STOP, automaticRestart false. This platform deadline works even if the application/guest is stuck.
- The service is started explicitly, not enabled at boot. The absolute platform deadline remains in scheduling and must be cleared/replaced before a future start after its expiry.
- Worker 2 remains TERMINATED.

Expected remaining conversion time is initially about 40-55 hours plus resume metadata checks; allow 2-3 days. The 72-hour compute ceiling is approximately $19.30 at the published e2-standard-8 on-demand rate of $0.26804568/hour. Storage, network/address and API operations add charges, so this is not a literal $50 billing hard cap. Same-region reads/uploads avoid deliberate cross-region transfer. Preserve a substantial budget reserve. Retained raw/compact objects and disks incur storage charges after compute stops; do not delete the archive to save money.

The remaining 84 ordinary-hour sources cover about 548.57 GB of compressed input, dated May 23-June 4. Completing these finishes the 1,691 ordinary-hour conversion plan. The 1,770 nonstandard/recovery objects remain preserved and require a separate audited scope; they are not silently added to this run.

## Validation and operations

Before launch: run repository tests; run --validate-only --max-sources 1 with indices 4,5 against real completed GCS sources; confirm both old VMs were stopped and only worker 1 restarted; verify platform deadline and systemd configuration.

On VM: checkout /home/sam_decoster_baruchmfe/microstructure-capstone; venv /home/sam_decoster_baruchmfe/poly-archive/.venv. Service: poly-archive-recovery.service. Application log: /home/sam_decoster_baruchmfe/poly-archive/logs/recovery-20261010.log. Supervisor emits assignment_progress, source_completed, assignment_finished and recovery_completed; failures retain resumable source manifests.

After shutdown, use VM status and GCS completion manifests to confirm success. A stopped VM alone does not mean successful conversion: inspect the service/log result or completion counts. Save outputs/errors before any future restart.

Sources: https://cloud.google.com/products/compute/pricing/general-purpose?hl=en and https://docs.cloud.google.com/compute/docs/instances/stop-start-instance.
