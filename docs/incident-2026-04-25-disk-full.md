# Incident: VPS Disk Full (gradeforai.com)

**Date:** 2026-04-25
**Severity:** Medium (no data loss; production services still running but write-blocked)
**Status:** Resolved
**Notified by:** Hostinger alert to Mark (KVM 4 VPS, <redacted>)

## Summary

The 193GB root volume on the gradeforai.com VPS reached 100% utilization. Cause: the daily backup retention policy (30 days local) had not kept pace with rapid growth of `scores.db`. Eighteen daily SQLite snapshots ranging 5GB to 15GB occupied 171GB of the 193GB disk. Resolved by deleting 16 oldest local snapshots (already mirrored to Cloudflare R2) and reducing local retention from 30 days to 3 days. No production data was lost; `scores.db` (live) and the full R2 archive (Apr 1 through Apr 25) are intact.

## Timeline

| Time (UTC) | Event |
|---|---|
| 2026-04-25 03:00 | Daily `agent-backup.service` fires. SQLite `.backup` partially writes `scores-2026-04-25.db` (2.2GB), then disk fills mid-write. |
| 2026-04-25 ~later | Hostinger automated alert triggered to Mark. |
| 2026-04-25 ~04:30 | Investigation began. `df -h` confirmed 193G/193G. |
| 2026-04-25 ~04:45 | Identified `/opt/agent-readiness/backups` as the source (171GB). R2 archive verified to contain every local snapshot plus older ones. |
| 2026-04-25 ~05:00 | Deleted 16 oldest local snapshots (Apr 4 + Apr 9 through Apr 23, both `scores-*.db` and `targets-*.tar.gz`). Disk dropped to 21% (39GB used). |
| 2026-04-25 ~05:05 | Edited `/opt/agent-readiness/backup.sh` retention `find ... -mtime +30 -delete` -> `+3 -delete`. Backup of original at `backup.sh.bak` on VPS. |

## Root Cause

`scores.db` grew much faster than anticipated when retention was set:

| Date | Snapshot size |
|---|---|
| 2026-04-04 | 4.8 GB |
| 2026-04-09 | 6.6 GB |
| 2026-04-17 | 11.0 GB |
| 2026-04-24 | 15.0 GB |

The DB roughly tripled in three weeks as the scorer worked through the 145K-URL backlog and accumulated multiple methodology versions of historical score rows. With 30 daily snapshots retained, the local backup directory had effectively unbounded growth proportional to DB size. At 15GB/snapshot * 30 days = 450GB ceiling on a 193GB disk — guaranteed to fill.

The retention number was chosen when DB was small (~1GB) and never revisited.

## Resolution

1. **Verified R2 archive completeness:** `rclone ls r2:gradeforai-backups/` showed Apr 1 through Apr 25 (25 snapshots), all matching local file sizes.
2. **Deleted 16 local snapshots** (Apr 4, Apr 9 through Apr 23) for both `scores-*.db` and `targets-*.tar.gz`. Kept Apr 24 + Apr 25.
3. **Patched `backup.sh`** on VPS: `-mtime +30 -delete` -> `-mtime +3 -delete` (both score and targets find clauses). Original saved to `backup.sh.bak`.
4. **Synced patched `backup.sh` to repo** so VPS and tracked source no longer drift.

## Outcome

- Disk: 100% -> 21% (154GB freed).
- Live `scores.db`: untouched, 16GB on `/opt/agent-readiness/data/scores.db`.
- Trending dataset integrity: preserved. All historical score rows are inside the live DB; daily snapshots are point-in-time copies, not the source of trend data.
- R2 retains every daily snapshot back to Apr 1, so historical state recovery is unaffected.
- Going forward, local backup ceiling is approximately 3 days * 15GB = 45GB, with continued daily uploads to R2.

## Data Safety Verification

The trending dataset that powers Competitive Position scoring and longitudinal observation lives in `scores.db` itself (rows in `scores`, `methodology_versions`, etc.), not in the daily snapshot files. Deleting old `.db` snapshot files removes redundant copies of past database state, not historical rows. Additionally:

- Cloudflare R2 bucket `gradeforai-backups` retains every snapshot indefinitely (90-day Bucket Lock immutability + no automated deletion).
- R2 was confirmed to hold all 16 deleted snapshots before any local deletion.

## Follow-ups / Prevention

- [ ] Add a disk-usage check to `agent-healthcheck.service` so we get an internal alert at 80% utilization before Hostinger does.
- [ ] Document an estimated DB growth rate in `docs/infra/BACKUP-AND-RECOVERY.md` and revisit retention any time DB doubles.
- [ ] Consider compressing local snapshots (`sqlite3 .backup` -> gzip) — SQLite databases typically compress 4-6x.
- [ ] Consider periodic `VACUUM` on `scores.db` to reclaim freed pages from rescore churn (not done during this incident to avoid disk pressure mid-recovery).
- [ ] Evaluate moving to incremental WAL-based backups instead of full `.backup` snapshots once DB exceeds ~25GB.

## Files Changed

- `/opt/agent-readiness/backup.sh` (VPS): retention 30d -> 3d, comment updated.
- `backup.sh` (repo): synced to match VPS, including R2 upload logic that had drifted out of source control.
- `docs/infra/BACKUP-AND-RECOVERY.md`: retention numbers updated, rationale added.
- `docs/incidents/2026-04-25-disk-full-vps.md`: this file.
