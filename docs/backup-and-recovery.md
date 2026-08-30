# Backup & Recovery Runbook

Last updated: 2026-04-25

## Architecture Overview

```
VPS (primary)                 Cloudflare R2 (off-site)
/opt/agent-readiness/         gradeforai-backups bucket
  data/scores.db              ├── scores-YYYY-MM-DD.db
  backups/                    ├── targets-YYYY-MM-DD.tar.gz
    scores-YYYY-MM-DD.db      └── (90-day Bucket Lock immutability)
    targets-YYYY-MM-DD.tar.gz
```

**Current status:** 2-1-1 (2 copies, 1 site, 1 off-site provider). Target: 3-2-1.

## What Gets Backed Up

| Asset | Backup method | Frequency | Retention |
|---|---|---|---|
| scores.db | `sqlite3 .backup` (safe hot copy) | Daily 3 AM UTC | 3 days local, permanent R2 |
| targets/*.csv | tar.gz archive | Daily 3 AM UTC | 3 days local, permanent R2 |
| harvest_state.json | included in targets tar | Daily 3 AM UTC | 3 days local, permanent R2 |
| scorer_state.json | included in targets tar | Daily 3 AM UTC | 3 days local, permanent R2 |

## Automated Systems

### Daily backup (systemd timer)
- **Service:** `agent-backup.service` / `agent-backup.timer`
- **Script:** `/opt/agent-readiness/backup.sh`
- **Schedule:** Daily at 3:00 AM UTC
- **Actions:** sqlite3 .backup -> local copy -> tar targets -> rclone to R2 -> prune local >3d
- **Retention rationale:** 30-day local retention was reduced to 3 days after 2026-04-25 disk-full incident. DB was growing ~7GB/week as scorer chewed backlog; 30 daily snapshots filled 193GB disk. R2 has full archive. See `docs/incidents/2026-04-25-disk-full-vps.md`.

### Monthly integrity check (cron)
- **Schedule:** 1st of month at 4:00 AM UTC
- **Script:** `/opt/agent-readiness/integrity_check.sh`
- **Log:** `/opt/agent-readiness/logs/integrity.log`
- **Actions:** PRAGMA integrity_check on scores.db, logs PASSED/FAILED with stats

## R2 Bucket Configuration

- **Bucket:** gradeforai-backups
- **Bucket Lock:** `retain-backups-90d` -- 90-day compliance immutability (no prefix filter)
- **API Token:** `vps-backup-writer` (Account API Token, Object Read & Write, bucket-scoped)
- **rclone config:** `/root/.config/rclone/rclone.conf` (remote name: `r2`)

## Recovery Procedures

### Scenario 1: Corrupted database (scores.db)

```bash
# 1. Stop all services
systemctl stop agent-scorer agent-dashboard agent-rescore agent-harvester

# 2. Move corrupted DB aside
mv /opt/agent-readiness/data/scores.db /opt/agent-readiness/data/scores.db.corrupted

# 3. Restore from most recent local backup
cp /opt/agent-readiness/backups/scores-$(date +%Y-%m-%d -d yesterday).db \
   /opt/agent-readiness/data/scores.db

# 4. If local backups are gone, restore from R2
rclone copy r2:gradeforai-backups/scores-YYYY-MM-DD.db /opt/agent-readiness/data/
mv /opt/agent-readiness/data/scores-YYYY-MM-DD.db /opt/agent-readiness/data/scores.db

# 5. Verify
sqlite3 /opt/agent-readiness/data/scores.db "PRAGMA integrity_check;"
sqlite3 /opt/agent-readiness/data/scores.db "SELECT COUNT(*) FROM businesses;"

# 6. Restart services
systemctl start agent-dashboard agent-scorer agent-rescore agent-harvester
```

### Scenario 2: VPS total loss

```bash
# 1. Provision new VPS, install deps (Python 3.11+, nginx, sqlite3, rclone)

# 2. Clone repo
git clone <repo-url> /opt/agent-readiness/

# 3. Restore database from R2
rclone copy r2:gradeforai-backups/scores-LATEST.db /opt/agent-readiness/data/
mv /opt/agent-readiness/data/scores-LATEST.db /opt/agent-readiness/data/scores.db

# 4. Restore targets
rclone copy r2:gradeforai-backups/targets-LATEST.tar.gz /tmp/
tar -xzf /tmp/targets-LATEST.tar.gz -C /opt/agent-readiness/data/

# 5. Set up rclone with new R2 token (create in Cloudflare dashboard)
# 6. Restore systemd services from deploy/ directory
# 7. Restore nginx config, SSL certs (certbot)
# 8. Verify and start services
```

### Scenario 3: Accidental deletion of R2 objects

Bucket Lock (retain-backups-90d) prevents deletion of any object less than 90 days old. Objects cannot be deleted or overwritten during the retention period, even by the account owner. No action needed for objects within the 90-day window.

For objects older than 90 days: they are only in R2 (local pruned at 30 days). If deleted, they are gone. Consider this acceptable -- 90 days of immutable history is sufficient for disaster recovery.

### Scenario 4: R2 token compromised

```bash
# 1. Immediately revoke token in Cloudflare dashboard (R2 > Manage R2 API Tokens)
# 2. Create new bucket-scoped Account API Token
# 3. Update /root/.config/rclone/rclone.conf with new credentials
# 4. Test: rclone lsd r2:gradeforai-backups
# 5. Verify next daily backup succeeds
```

## Verification Commands

```bash
# Check backup timer status
systemctl status agent-backup.timer

# List recent local backups
ls -lh /opt/agent-readiness/backups/ | tail -5

# List R2 backups
rclone ls r2:gradeforai-backups | tail -5

# Check R2 total size
rclone size r2:gradeforai-backups

# View integrity check log
cat /opt/agent-readiness/logs/integrity.log

# Manual integrity check
sqlite3 /opt/agent-readiness/data/scores.db "PRAGMA integrity_check;"

# Check DB stats
sqlite3 /opt/agent-readiness/data/scores.db "SELECT COUNT(*) FROM businesses; SELECT COUNT(*) FROM scores;"
```

## Quarterly Restore Drill (Task #13.4)

Not yet implemented. Plan: download a recent R2 backup to /tmp on VPS, run integrity_check, verify row counts match production, delete test copy. Should take <5 minutes.

## Future Improvements

- **Second off-site provider** (Backblaze B2) for true 3-2-1 -- deferred, evaluate at $10K/mo
- **Weekly pull to Mac** -- automated rsync of latest backup to local machine
- **Alerting** -- email/Slack notification on integrity check failure or backup failure
