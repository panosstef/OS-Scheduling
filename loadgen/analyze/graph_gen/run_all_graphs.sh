#!/bin/bash

set -e

# Check if at least one pattern argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <pattern1> [pattern2] ... [--exclude <substring1>] [--exclude <substring2>] ..."
    echo "Example: $0 20 50 60 80 --exclude user --exclude debug"
    exit 1
fi

PATTERNS=()
EXCLUDES=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --exclude)
            if [[ -z "$2" || "$2" == --* ]]; then
                echo "Error: --exclude requires a value"
                exit 1
            fi
            EXCLUDES+=("$2")
            shift 2
            ;;
        *)
            PATTERNS+=("$1")
            shift
            ;;
    esac
done

if [ ${#PATTERNS[@]} -eq 0 ]; then
    echo "Error: at least one pattern is required"
    exit 1
fi

# Filter an array of files, removing any whose path contains an excluded substring
filter_files() {
    local -n _files=$1
    local filtered=()
    for f in "${_files[@]}"; do
        local exclude=false
        for ex in "${EXCLUDES[@]}"; do
            if [[ "$f" == *"$ex"* ]]; then
                exclude=true
                break
            fi
        done
        [[ "$exclude" == false ]] && filtered+=("$f")
    done
    _files=("${filtered[@]}")
}

echo "Starting graph generation with patterns: ${PATTERNS[*]}"
if [ ${#EXCLUDES[@]} -gt 0 ]; then
    echo "Excluding files matching: ${EXCLUDES[*]}"
fi

# Change to the graph_gen directory
cd "$(dirname "$0")"

# Get the base log directory path (go up two levels from graph_gen)
LOG_DIR="../../log"

echo "Running graph_cpu_util.py..."
files=()
for pattern in "${PATTERNS[@]}"; do
    files+=(${LOG_DIR}/cpu_util/*${pattern}*.csv)
done
filter_files files
python3 graph_cpu_util.py "${files[@]}"
if [ $? -eq 0 ]; then
    echo "✓ graph_cpu_util.py completed successfully"
else
    echo "✗ graph_cpu_util.py failed with exit code $?"
fi
echo ""

echo "Running graph_general_stats.py..."
files=()
for pattern in "${PATTERNS[@]}"; do
    files+=(${LOG_DIR}/stats_general/*${pattern}*.txt)
done
filter_files files
python3 graph_general_stats.py "${files[@]}"
if [ $? -eq 0 ]; then
    echo "✓ graph_general_stats.py completed successfully"
else
    echo "✗ graph_general_stats.py failed with exit code $?"
fi
echo ""

echo "Running graph_per_proc_stats.py..."
files=()
for pattern in "${PATTERNS[@]}"; do
    files+=(${LOG_DIR}/per_proc_stats/*${pattern}*.csv)
done
filter_files files
python3 graph_per_proc_stats.py "${files[@]}"
if [ $? -eq 0 ]; then
    echo "✓ graph_per_proc_stats.py completed successfully"
else
    echo "✗ graph_per_proc_stats.py failed with exit code $?"
fi
echo ""

echo "Running graph_per_proc_times.py..."
files=()
for pattern in "${PATTERNS[@]}"; do
    files+=(${LOG_DIR}/per_proc_times/*${pattern}*.csv)
done
filter_files files
python3 graph_per_proc_times.py "${files[@]}"
if [ $? -eq 0 ]; then
    echo "✓ graph_per_proc_times.py completed successfully"
else
    echo "✗ graph_per_proc_times.py failed with exit code $?"
fi
echo ""

echo "Running graph_sch_latencies.py..."
files=()
for pattern in "${PATTERNS[@]}"; do
    files+=(${LOG_DIR}/per_proc_sch_latencies/*${pattern}*.csv)
done
filter_files files
python3 graph_sch_latencies.py "${files[@]}"
if [ $? -eq 0 ]; then
    echo "✓ graph_sch_latencies.py completed successfully"
else
    echo "✗ graph_sch_latencies.py failed with exit code $?"
fi
echo ""

echo "Graph generation complete!"
