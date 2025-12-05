#!/bin/bash
# Simple script to log sched_ext events while running a function

set -e

# Check if sched_ext is loaded
if [[ ! -e /sys/kernel/sched_ext/root/ops ]]; then
    echo "Error: sched_ext scheduler is not loaded"
    echo "/sys/kernel/sched_ext/root/ops does not exist"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="log.txt"

# Check for command line argument
if [[ $# -eq 0 ]]; then
    echo "Usage: $0 <duration>"
    echo "  duration: Time in seconds to run the test"
    exit 1
fi

DURATION="$1"

# Validate that duration is a number
if ! [[ "$DURATION" =~ ^[0-9]+$ ]]; then
    echo "Error: Duration must be a positive integer"
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo "Cleaning up..."
    # Kill the cat process
    if [[ -n "$LOG_PID" ]]; then
        kill $LOG_PID 2>/dev/null || true
        wait $LOG_PID 2>/dev/null || true
    fi
    # Also kill any remaining cat processes on trace_pipe as fallback
    pkill -f "cat /sys/kernel/debug/tracing/trace_pipe" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

# Start logging in background
cat /sys/kernel/debug/tracing/trace_pipe > "$LOG_FILE" &
LOG_PID=$!

sleep 2  # Give logging a moment to start
echo "Running: ./run_with_sched_ext ./launch_function.out $DURATION"

# Run the command and capture output
OUTPUT=$(../loadgen/payload/run_with_sched_ext ../loadgen/payload/launch_function.out $DURATION)
echo "Function output: $OUTPUT"

# Extract the first integer (PID) from the output
PID=$(echo "$OUTPUT" | grep -oE '[0-9]+' | head -n1)

if [[ -z "$PID" ]]; then
    echo "Error: Could not extract PID from output: $OUTPUT"
    exit 1
fi

echo "Extracted PID: $PID"

sleep 20

# Stop logging
echo "Stopping logging..."
if [[ -n "$LOG_PID" ]]; then
    kill $LOG_PID 2>/dev/null || true
    wait $LOG_PID 2>/dev/null || true
fi

# Filter the log file for the specific PID
FILTERED_LOG="log_filtered.txt"
echo "Filtering log for PID $PID..."

grep "$PID" "$LOG_FILE" > "$FILTERED_LOG" || {
    echo "No entries found for PID $PID"
    exit 0
}

#Delete original (non-filtered) log file
rm "$LOG_FILE"

# Delete lines before "enabling task" and after "exiting task"
sed -i '/init task/,$!d; /exiting task/q' "$FILTERED_LOG"

# Convert timestamps to offset from first timestamp
echo "Converting timestamps to offset from first timestamp..."
TEMP_FILE="${FILTERED_LOG}.temp"

awk '
BEGIN { first_ts = -1 }
{
    # Extract timestamp (assumes format like "12345.678901:")
    if (match($0, /[0-9]+\.[0-9]+:/)) {
        ts_str = substr($0, RSTART, RLENGTH-1)
        ts = ts_str + 0

        if (first_ts == -1) {
            first_ts = ts
            offset = 0
        } else {
            offset = ts - first_ts
        }

        # Replace original timestamp with offset from first timestamp
        sub(/[0-9]+\.[0-9]+:/, sprintf("%.6f:", offset))
    }
    print
}
' "$FILTERED_LOG" > "$TEMP_FILE"

mv "$TEMP_FILE" "$FILTERED_LOG"

echo "Filtered log saved to: $FILTERED_LOG"