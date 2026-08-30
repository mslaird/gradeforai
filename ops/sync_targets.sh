#!/bin/bash
# Sync harvested target CSVs from Mac to VPS every run
# The harvester runs locally (DDG blocks VPS IPs), scorer runs on VPS

VPS="${GFA_VPS:?set GFA_VPS, e.g. user@host}"
LOCAL_TARGETS="$HOME/agent-readiness/data/targets/"
REMOTE_TARGETS="/opt/agent-readiness/data/targets/"

rsync -az --update "$LOCAL_TARGETS" "$VPS:$REMOTE_TARGETS" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "[$(date '+%H:%M:%S')] Synced targets to VPS"
else
    echo "[$(date '+%H:%M:%S')] Sync failed"
fi
