#!/bin/bash

# Check if script is run as root
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root to access ftrace functionality."
    exit 1
fi

# Check if program name is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <program> [program_args...]"
    echo "Example: $0 ls -l"
    exit 1
fi

# Set trace directory
TRACEDIR="/sys/kernel/tracing"

# Helper function to safely write to files with error handling
safe_write() {
    local file="$1"
    local value="$2"

    if [ ! -f "$file" ]; then
        echo "Warning: File $file does not exist."
        return 1
    fi

    echo "$value" > "$file" 2>/dev/null || {
        echo "Warning: Could not write '$value' to $file"
        return 1
    }
    return 0
}

# Clean up function to ensure tracing is stopped
cleanup() {
    echo "Stopping trace..."
    safe_write "$TRACEDIR/tracing_on" "0"
    safe_write "$TRACEDIR/set_event" ""
    echo "Trace stopped. Results saved to trace_output.txt"
}

# Make sure the ftrace directory is mounted
if [ ! -d "$TRACEDIR" ]; then
    echo "Mounting debugfs..."
    mount -t debugfs nodev /sys/kernel/debug
    if [ ! -d "$TRACEDIR" ]; then
        echo "Error: Could not access $TRACEDIR"
        exit 1
    fi
fi

# Make sure the tracing is stopped before we begin
safe_write "$TRACEDIR/tracing_on" "0"

# Clear trace buffer
safe_write "$TRACEDIR/trace" ""

# Increase buffer size to 16MB
safe_write "$TRACEDIR/buffer_size_kb" "32768"

# Reset to nop tracer (no function graph)
safe_write "$TRACEDIR/current_tracer" "nop"

# Set options to show full process names
if [ -d "$TRACEDIR/options" ]; then
    # Try to enable print-tgid if available (shows thread group ID)
    safe_write "$TRACEDIR/options" "record-cmd"
    safe_write "$TRACEDIR/options" "record-tgid"
    safe_write "$TRACEDIR/saved_cmdlines_size" "256"

    # Try to increase comm field width if the option exists
    if [ -f "$TRACEDIR/options/comm-max" ]; then
        safe_write "$TRACEDIR/options/comm-max" "32"
    fi
fi

# Clear any previous events
safe_write "$TRACEDIR/set_event" ""

# Add each event to the trace
EVENTS=(
    "sched:sched_wakeup_new"
    "sched:sched_waking"
    "sched:sched_migrate_task"
    "sched:sched_process_hang"
    "sched:sched_process_exec"
    "sched:sched_process_fork"
    "sched:sched_process_wait"
    "sched:sched_process_exit"
    "sched:sched_process_free"
    "task:task_newtask"
    "task:task_rename"
    "error_report"
)

# Add events one by one with error handling
for event in "${EVENTS[@]}"; do
    if echo "$event" >> "$TRACEDIR/set_event" 2>/dev/null; then
        echo "Enabled event: $event"
    else
        echo "Warning: Could not enable event: $event"
    fi
done

# Set tracing to be enabled
if safe_write "$TRACEDIR/tracing_on" "1"; then
    echo "Starting trace for: $@"
    echo "----------------------------------------"

    # Execute the specified program
    "$@"
    PROGRAM_EXIT_CODE=$?

    echo "----------------------------------------"
    echo "Program completed with exit code: $PROGRAM_EXIT_CODE"
    sleep 3
    # Stop tracing
    safe_write "$TRACEDIR/tracing_on" "0"

    # Save the trace output to a file
    cat "$TRACEDIR/trace" > "trace_output.txt"

    # Clean up
    cleanup
else
    echo "Error: Could not enable tracing"
    exit 1
fi

exit $PROGRAM_EXIT_CODE