#!/bin/bash

set -e

# Initialize variables
OUTPUT_FILE=""
POSITIONAL_ARGS=()

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

# Restore positional arguments
set -- "${POSITIONAL_ARGS[@]}"

# Check if an argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 [-o|--output OUTPUT_FILE] <executable> [arguments]"
    echo "Example: $0 python3 my_script.py"
    echo "Example with custom output: $0 -o my_trace.dat python3 my_script.py"
    exit 1
fi

# Ensure script is run with sudo
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root or with sudo"
    exit 1
fi

# Throw an error if not output file is specified if not specified
if [ -z "$OUTPUT_FILE" ]; then
    echo "No output file specified. Exiting..."
    exit 1
fi

#Comprehensive scheduling events to trace
SCHED_EVENTS=(
    sched:sched_process_exec
    sched:sched_process_fork
    # sched:sched_process_wait
    sched:sched_process_exit
    # sched:sched_process_free
    sched:sched_migrate_task
    sched:sched_switch
    # sched:sched_wakeup_new
    # sched:sched_wakeup
    # sched:sched_wait_task
    #syscalls:sys_exit_execve
    #syscalls:sys_enter_execve
    # sched:sched_stat_runtime
    # sched:sched_stat_blocked
    # sched:sched_stat_iowait
    # sched:sched_stat_sleep
    # sched:sched_stat_wait
    # task_newtask
    # task_rename
    # error_report
)

# Build event arguments correctly
EVENT_ARGS=""
for event in "${SCHED_EVENTS[@]}"; do
    EVENT_ARGS="$EVENT_ARGS -e $event"
done

# Start tracing
echo "Starting trace for: $*"
echo "Output will be saved to: $OUTPUT_FILE"
trace-cmd record -b 10000 $EVENT_ARGS -o "$OUTPUT_FILE" -F -c "$@"

# Check for errors
if [ $? -ne 0 ]; then
    echo "Error: trace-cmd failed to start or encountered an issue."
    exit 1
fi
echo "Trace saved to: $OUTPUT_FILE"
#echo "To get the report use: trace-cmd report -R -t -w --ts-check > trace.txt"
