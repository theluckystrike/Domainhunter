#!/bin/bash
# Domain Hunter — Quick Health Check (run daily)
# Usage: bash scripts/health_check.sh

echo "=== DOMAIN HUNTER HEALTH CHECK ==="
echo "Time: $(date)"
echo ""

# 1. Daemon running?
PID=$(pgrep -f daemon_scheduler)
if [ -n "$PID" ]; then
    echo "✓ Daemon: RUNNING (PID $PID)"
    echo "  Memory: $(ps -p $PID -o rss= | awk '{printf "%.1f MB", $1/1024}')"
    echo "  Uptime: $(ps -p $PID -o etime= | xargs)"
else
    echo "✗ Daemon: NOT RUNNING"
fi

# 2. Heartbeat fresh?
HB_FILE="$HOME/Desktop/domainhunter/logs/.daemon_heartbeat"
if [ -f "$HB_FILE" ]; then
    HB_AGE=$(( $(date +%s) - $(stat -f %m "$HB_FILE") ))
    if [ $HB_AGE -lt 300 ]; then
        echo "✓ Heartbeat: Fresh (${HB_AGE}s ago)"
    else
        echo "⚠ Heartbeat: STALE (${HB_AGE}s ago)"
    fi
else
    echo "✗ Heartbeat: FILE NOT FOUND"
fi

# 3. Disk usage
echo ""
echo "--- Disk Usage ---"
echo "  Data dir: $(du -sh $HOME/Desktop/domainhunter/data/ 2>/dev/null | cut -f1)"
echo "  Logs dir: $(du -sh $HOME/Desktop/domainhunter/logs/ 2>/dev/null | cut -f1)"
echo "  Total project: $(du -sh $HOME/Desktop/domainhunter/ 2>/dev/null | cut -f1)"

# 4. Log file sizes (warn if any > 10MB)
echo ""
echo "--- Log Files ---"
BIG_LOGS=$(find "$HOME/Desktop/domainhunter/logs" -name "*.log" -size +10M 2>/dev/null)
if [ -n "$BIG_LOGS" ]; then
    echo "⚠ Large log files (>10MB):"
    echo "$BIG_LOGS" | while read f; do echo "    $(du -h "$f" | cut -f1)  $(basename "$f")"; done
else
    echo "✓ All log files < 10MB"
fi
echo "  daemon_scheduler.log: $(wc -l < "$HOME/Desktop/domainhunter/logs/daemon_scheduler.log" 2>/dev/null || echo 0) lines"
echo "  post_catch JSON files: $(ls "$HOME/Desktop/domainhunter/logs"/post_catch_*.json 2>/dev/null | wc -l | xargs) files"

# 5. File descriptors (leak check)
if [ -n "$PID" ]; then
    FD_COUNT=$(lsof -p $PID 2>/dev/null | wc -l | xargs)
    echo ""
    echo "--- File Descriptors ---"
    if [ "$FD_COUNT" -lt 50 ]; then
        echo "✓ Open FDs: $FD_COUNT (healthy)"
    else
        echo "⚠ Open FDs: $FD_COUNT (possible leak)"
    fi
fi

# 6. Last task runs
echo ""
echo "--- Last Task Runs ---"
if [ -f "$HB_FILE" ]; then
    grep "last_run" "$HB_FILE" | while read line; do echo "  $line"; done
fi

# 7. Data growth check
echo ""
echo "--- Data Subdirectories ---"
du -sh "$HOME/Desktop/domainhunter/data"/*/ 2>/dev/null | sort -h | while read line; do echo "  $line"; done

# 8. LaunchAgent status
echo ""
echo "--- LaunchAgent ---"
if launchctl list 2>/dev/null | grep -q "com.domainhunter.daemon"; then
    echo "✓ com.domainhunter.daemon: loaded"
else
    echo "✗ com.domainhunter.daemon: NOT loaded"
fi

echo ""
echo "=== END ==="
