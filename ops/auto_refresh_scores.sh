#!/bin/bash
# Auto-refresh industry/city/benchmark scores and rebuild the website.
# Run on VPS after scoring batches complete, or via cron/systemd timer.
#
# Usage:
#   ./auto_refresh_scores.sh              # Normal run
#   ./auto_refresh_scores.sh --force      # Rebuild even if no changes
#   ./auto_refresh_scores.sh --notify     # Email Mark if scores shifted >2pts

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

JSON_FILE="website/industry_data.json"
LOG_FILE="data/score_refresh.log"
NOTIFY_EMAIL="mark@gradeforai.com"
THRESHOLD=2  # points of change to trigger notification

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Parse args
FORCE=false
NOTIFY=false
for arg in "$@"; do
    case "$arg" in
        --force) FORCE=true ;;
        --notify) NOTIFY=true ;;
    esac
done

log "Starting score refresh..."

# Save previous JSON for comparison
PREV_JSON=""
if [ -f "$JSON_FILE" ]; then
    PREV_JSON=$(cat "$JSON_FILE")
fi

# Run the update script
if ! python3 update_industry_scores.py 2>&1 | tee -a "$LOG_FILE"; then
    log "ERROR: update_industry_scores.py failed"
    exit 1
fi

# Check if anything changed
NEW_JSON=$(cat "$JSON_FILE")
if [ "$PREV_JSON" = "$NEW_JSON" ] && [ "$FORCE" != "true" ]; then
    log "No score changes detected. Skipping rebuild."
    exit 0
fi

# SAFETY GUARD: Block publish if national avg shifted more than MAX_DRIFT points.
# This prevents inflated v5.0 scores from overwriting published data.
# Remove this guard after v5.1 calibration is validated.
MAX_DRIFT=15

if [ -n "$PREV_JSON" ]; then
    OLD_AVG=$(echo "$PREV_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('national',{}).get('avg',0))" 2>/dev/null || echo "0")
    NEW_AVG=$(echo "$NEW_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('national',{}).get('avg',0))" 2>/dev/null || echo "0")
    DRIFT=$((NEW_AVG - OLD_AVG))
    ABS_DRIFT=${DRIFT#-}

    if [ "$ABS_DRIFT" -gt "$MAX_DRIFT" ] && [ "$FORCE" != "true" ]; then
        log "BLOCKED: National average shifted by ${DRIFT} points (${OLD_AVG} -> ${NEW_AVG}). Exceeds safety threshold of ${MAX_DRIFT}."
        log "This likely means v5.0 calibration is still inflated. Restoring previous JSON."
        echo "$PREV_JSON" > "$JSON_FILE"
        # Notify
        if [ "$NOTIFY" = "true" ] && command -v mail &>/dev/null; then
            echo "BLOCKED: Score refresh attempted but national average shifted ${DRIFT} points (${OLD_AVG} -> ${NEW_AVG}).

This exceeds the safety threshold of ${MAX_DRIFT} points. The previous scores have been restored.

This likely means v5.1 calibration has not been applied yet. Do NOT use --force until the scoring engine is recalibrated.

Timestamp: $(date)" | mail -s "GradeForAI: Score refresh BLOCKED (drift: ${DRIFT} pts)" "$NOTIFY_EMAIL" 2>/dev/null || true
        fi
        exit 1
    fi
fi

log "Scores updated (drift: ${DRIFT:-0} pts). Rebuilding website..."

# Rebuild
if ! python3 website/build.py 2>&1 | tee -a "$LOG_FILE"; then
    log "ERROR: build.py failed"
    exit 1
fi

log "Website rebuilt successfully."

# Check for significant changes and notify
if [ "$NOTIFY" = "true" ] && [ -n "$PREV_JSON" ]; then
    # Compare national average (simple check)
    OLD_AVG=$(echo "$PREV_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('national',{}).get('avg',0))" 2>/dev/null || echo "0")
    NEW_AVG=$(echo "$NEW_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('national',{}).get('avg',0))" 2>/dev/null || echo "0")
    DIFF=$((NEW_AVG - OLD_AVG))
    ABS_DIFF=${DIFF#-}

    if [ "$ABS_DIFF" -ge "$THRESHOLD" ]; then
        log "National average shifted by ${DIFF} points (${OLD_AVG} -> ${NEW_AVG}). Sending notification."
        # Send email via system mail if available
        if command -v mail &>/dev/null; then
            echo "GradeForAI score refresh detected a significant shift.

National average: ${OLD_AVG} -> ${NEW_AVG} (${DIFF} points)
Timestamp: $(date)

The website has been automatically rebuilt with updated scores.
Review at https://gradeforai.com/reports/benchmark" | mail -s "GradeForAI: Score shift detected (${DIFF} pts)" "$NOTIFY_EMAIL" 2>/dev/null || true
        fi
    else
        log "National average stable (${OLD_AVG} -> ${NEW_AVG}, delta: ${DIFF})."
    fi
fi

log "Score refresh complete."
