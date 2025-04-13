#!/bin/bash
ulimit -n 16384

iterations=1
groups=250

# Processes
results=()
echo "Running hackbench with --process $iterations times..."

for ((i=1; i<=iterations; i++)); do
    TIME=$(hackbench  --pipe -g $groups | grep "Time:" | awk '{print $2}')
    echo "Iteration $i: $TIME s"
    results+=($TIME)
done

AVG=$(echo "${results[@]}" | awk '{sum=0; for (i=1; i<=NF; i++) sum+=$i; print sum/NF}')
STDDEV=$(echo "${results[@]}" | awk -v avg=$AVG '{sum=0; for (i=1; i<=NF; i++) sum+=($i-avg)^2; print sqrt(sum/NF)}')

echo "Average execution time (process): $AVG seconds"
echo "Standard deviation (process): $STDDEV seconds"

#Threads
results=()
echo -e "\nRunning hackbench with --threads $iterations times..."

for ((i=1; i<=iterations; i++)); do
    TIME=$(hackbench --pipe --threads -g $groups | grep "Time:" | awk '{print $2}')
    echo "Iteration $i: $TIME s"
    results+=($TIME)
done

AVG=$(echo "${results[@]}" | awk '{sum=0; for (i=1; i<=NF; i++) sum+=$i; print sum/NF}')
STDDEV=$(echo "${results[@]}" | awk -v avg=$AVG '{sum=0; for (i=1; i<=NF; i++) sum+=($i-avg)^2; print sqrt(sum/NF)}')

echo "Average execution time (threads): $AVG seconds"
echo "Standard deviation (threads): $STDDEV seconds"
