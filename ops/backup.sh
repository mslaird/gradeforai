#!/bin/bash
# Daily backup of Agent Readiness database
# Backs up locally + uploads to Cloudflare R2
# Keeps last 3 days locally (post-2026-04-25 disk-full incident), R2 retains everything

BACKUP_DIR="/opt/agent-readiness/backups"
DB_PATH="/opt/agent-readiness/data/scores.db"
DATE=$(date +%Y-%m-%d)

mkdir -p "$BACKUP_DIR"

if [ -f "$DB_PATH" ]; then
    # Use SQLite backup command for safe copy (no corruption from active writes)
    sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/scores-$DATE.db'"
    echo "$(date): Backed up to $BACKUP_DIR/scores-$DATE.db"

    # Also back up target lists and state files
    tar -czf "$BACKUP_DIR/targets-$DATE.tar.gz" -C /opt/agent-readiness/data targets/ harvest_state.json scorer_state.json 2>/dev/null

    # Upload to Cloudflare R2
    rclone copy "$BACKUP_DIR/scores-$DATE.db" r2:gradeforai-backups/
    rclone copy "$BACKUP_DIR/targets-$DATE.tar.gz" r2:gradeforai-backups/
    echo "$(date): Uploaded to R2"

    # Clean local backups older than 3 days
    find "$BACKUP_DIR" -name "scores-*.db" -mtime +3 -delete
    find "$BACKUP_DIR" -name "targets-*.tar.gz" -mtime +3 -delete

    RECORDS=$(sqlite3 "$DB_PATH" 'SELECT COUNT(*) FROM businesses;')
    echo "$(date): Backup complete. DB size: $(du -h "$DB_PATH" | cut -f1). Records: $RECORDS"
else
    echo "$(date): ERROR - No database found at $DB_PATH"
fi
