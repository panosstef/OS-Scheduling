#!/bin/bash

set -e

# Check if pattern argument is provided
if [ $# -ne 1 ]; then
    PATTTERN=""
fi

PATTERN=$1

echo "Starting graph generation with pattern: $PATTERN"

# Change to the graph_gen directory
cd "$(dirname "$0")"

# Get the base log directory path (go up two levels from graph_gen)
LOG_DIR="../../log"

echo "Running graph_cpu_util.py..."
python3 graph_cpu_util.py ${LOG_DIR}/cpu_util/*${PATTERN}*.csv
if [ $? -eq 0 ]; then
    echo "✓ graph_cpu_util.py completed successfully"
else
    echo "✗ graph_cpu_util.py failed with exit code $?"
fi
echo ""

echo "Running graph_general_stats.py..."
python3 graph_general_stats.py ${LOG_DIR}/stats_general/*${PATTERN}*.txt
if [ $? -eq 0 ]; then
    echo "✓ graph_general_stats.py completed successfully"
else
    echo "✗ graph_general_stats.py failed with exit code $?"
fi
echo ""

echo "Running graph_per_proc_stats.py..."
python3 graph_per_proc_stats.py ${LOG_DIR}/per_proc_stats/*${PATTERN}*.csv
if [ $? -eq 0 ]; then
    echo "✓ graph_per_proc_stats.py completed successfully"
else
    echo "✗ graph_per_proc_stats.py failed with exit code $?"
fi
echo ""

echo "Running graph_per_proc_times.py..."
python3 graph_per_proc_times.py ${LOG_DIR}/per_proc_times/*${PATTERN}*.csv
if [ $? -eq 0 ]; then
    echo "✓ graph_per_proc_times.py completed successfully"
else
    echo "✗ graph_per_proc_times.py failed with exit code $?"
fi
echo ""

echo "Running graph_sch_latencies.py..."
python3 graph_sch_latencies.py ${LOG_DIR}/per_proc_sch_latencies/*${PATTERN}*.csv
if [ $? -eq 0 ]; then
    echo "✓ graph_sch_latencies.py completed successfully"
else
    echo "✗ graph_sch_latencies.py failed with exit code $?"
fi
echo ""

echo "Graph generation complete!"
