# Multi-VM cloud conversion runbook

## Live reverse-order run (2026-10-01)

The original four-process job was gracefully stopped. Its completed source manifests remain under `ordinary-v1-20260927`; incomplete source attempts will be retried when reached. Both VMs now run revision `5cb9a35` and the same production run ID using immutable plan `runs/ordinary-v1-20260927/plan-6-workers-reverse-20261001.json`. The converter schedules each VM's selected sources in reverse chronological order.

| VM | Plan indices | Coordinator PID at launch | Log |
|---|---|---:|---|
| `poly-archive-worker-1` | `0,1,2,3` | `261903` | `~/poly-archive/logs/ordinary-v1-20260927-reverse-vm1.log` |
| `poly-archive-worker-2` | `4,5` | `1195` | `~/poly-archive/logs/ordinary-v1-20260927-reverse-vm2.log` |

The six assignments are disjoint. At launch, the six processes were each reading a different August 16 hour at about 90–98% of one CPU; memory and disk had ample headroom. The first large-file period is June 4 and earlier (roughly 5–8 GB per regular source), after a gap from June 5–17. June 18 onward contains 1,014,113,826,124 compressed bytes. The two-worker pilot's measured 2.46 MB/s would take about 4.8 days for those bytes; scaling linearly to six workers yields 1.6 days, so use 2–3 days as an initial working range rather than a firm ETA. Update the estimate from completed input bytes and resource use as this run proceeds.

An hourly Codex heartbeat named `Monitor Polymarket conversion` checks both processes, logs, resource headroom, and the transition into the large-file period. It stays quiet during normal progress and notifies on failures, stalls, low resources, completion, or first entry into June 4 or earlier. This monitor does not change VM state.

The historical preparation and pilot instructions below are retained for provenance. Keep the raw bucket immutable.

## Prepared state (2026-10-01)

- `poly-archive-worker-1`, `us-east1-c`, `e2-standard-8`, 200 GB balanced disk: running the original job. Its process was launched from revision `2fc8898`; updating the checkout does not update running processes.
- `poly-archive-worker-2`, `us-east1-c`, `e2-standard-4`, 150 GB standard disk: configured with revision `61d79a1`, Python 3.12 virtual environment, and `cloud_worker_requirements.txt` equivalents; stopped after a successful plan-only check. This smaller VM is for the pilot while the global CPU quota is 12.
- Plan object: `gs://poly-capstone-compact/runs/ordinary-v1-20260927/plan-12-workers.json`. It has 12 byte-balanced assignments, each ~242 GB. All 1,691 ordinary sources are present exactly once; 1,770 nonstandard objects are listed separately and not scheduled.
- Global `CPUS_ALL_REGIONS` quota is 12 vCPUs, with 8 used by worker 1. The Cloud Quotas preference `poly-archive-global-cpus-32` was tried at 32 and then 16; Google denied both immediately without a detailed reason. Billing is enabled. The regional quota is not the immediate blocker. Do not assume an additional large VM can be started until the global quota is raised through Google Cloud support or the console.

## Pilot gate (only after user approval)

1. Start `poly-archive-worker-2` and verify its checkout, virtual environment, service-account access, free disk, and quota status.
2. Run `--pilot-source` for the already completed August 16 09:00 UTC source with its existing pilot run ID. It must return `skipped_valid_completion`, proving resume validation against real GCS objects without rereading raw data.
3. Pull the latest tested `cloud-pipeline` revision and use a new pilot run ID with `--workers 2 --max-sources 2` on worker 2. This exercises the normal process-pool/cancellation path on the two latest sources (August 16 21:00 and 20:00, 774,827,747 compressed bytes total). Use unbuffered logging and a 20-minute runtime cap with graceful SIGTERM first. Check row counts, duplicate and event accounting, output sizes, completion manifests, CPU usage, and memory/disk peaks. The single-source `--pilot-source` path alone does not measure production coordination overhead; see `CLOUD_THROUGHPUT_AUDIT.md`.
4. Stop worker 2 after the pilot and report measured MB/s, cost rate, and whether standard-disk I/O or memory is limiting.

## Production cutover gate (separate approval)

1. Require the global CPU quota increase to be granted before creating larger parallel capacity. Four `e2-standard-8` VMs would be the 32-vCPU upper layout, not current entitlement; begin with enough VMs to measure scaling and add more only if throughput improves materially. Standard persistent disks avoid the current balanced-disk quota cap; check disk throughput and free space in the pilot. The 12-way plan is a prepared target, not a reason to run 12 processes on the current 12 vCPUs.
2. Request graceful shutdown of the old four-process run and wait for its parent and child processes to exit. Never overlap the old 4-way plan with the new 12-way plan because their assignments differ.
3. Validate a sample of existing completion manifests with revision `61d79a1` before scheduling production. Use the immutable 12-way plan and disjoint `--worker-indices` sets per VM. Do not regenerate the plan while workers are running.
4. Resume with the same `ordinary-v1-20260927` run ID so validated completed sources are skipped. Record each VM's index set, Git revision, launch command, and log path. Track source completions and compressed input bytes, not only source count.
5. Stop or resize idle VMs as soon as their assigned work ends. Preserve completion manifests and raw data. Process the 1,770 nonstandard objects only under a separate audited plan.

## Safety notes

The converter stages a source's Parquet output locally until upload. A graceful stop abandons only the in-progress source; a completed source is resumable from its verified manifest. For the new revision, `complete()` reloads each output object's metadata before accepting its recorded size, fixing a false-negative resume check. The old running process is unaffected until cutover. A stopped VM still incurs persistent-disk storage charges but not VM CPU charges.
