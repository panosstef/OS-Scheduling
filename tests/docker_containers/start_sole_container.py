import time
import container_runners
import sys
import numpy as np
import json
import csv
from multiprocessing import Pool
from os import sched_getaffinity
from functools import partial

# Import color codes from container_runners
from container_runners import GREEN, RED, CYAN, YELLOW, RESET

SCRIPT_CPU = "python -c 'def fib(n): return n if n < 2 else fib(n-1) + fib(n-2); print(fib(30))'"
SCRIPT_IO = (
    "python -c '"
    "with open(\"/tmp/testfile.txt\", \"w\") as f: "
    "    f.write(\"A\" * 10**7); "  # Write a 10MB file
    "with open(\"/tmp/testfile.txt\", \"r\") as f: "
    "    data = f.read(); "
    "print(f\"Read {len(data)} bytes\")'"
)


def run_tests_with_pool(run_container):

    times_pool = []
    runtimes_pool = []

    for _ in range(25):
        start_time = time.time()
        with Pool(processes=len(sched_getaffinity(0))) as pool:
            try:
                runtimes_pool += pool.map(run_container, [0])
            except Exception as e:
                print(f"Error during pool execution: {e}")
                return None
        end_time = time.time()
        times_pool += [end_time - start_time]

    results = {
        "method": "with_pool",
        "average_execution_time": float(np.average(times_pool)),
        "average_without_overhead": float(np.average(runtimes_pool)),
        "median_execution_time": float(np.median(times_pool)),
        "std_dev_execution_time": float(np.std(times_pool)),
        "max_execution_time": float(max(times_pool)),
        "percentile_99_execution_time": float(np.percentile(times_pool, 99)),
        "percentile_95_execution_time": float(np.percentile(times_pool, 95))
    }

    return results


def run_tests_without_pool(run_container):

    times_no_pool = []
    
    for _ in range(25):
        start_time = time.time()
        try:
            _ = [run_container()]
        except Exception as e:
            print(f"Error during container execution: {e}")
            return None
        end_time = time.time()
        times_no_pool += [end_time - start_time]

    results = {
        "method": "without_pool",
        "average_execution_time": float(np.average(times_no_pool)),
        "median_execution_time": float(np.median(times_no_pool)),
        "std_dev_execution_time": float(np.std(times_no_pool)),
        "max_execution_time": float(max(times_no_pool)),
        "percentile_99_execution_time": float(np.percentile(times_no_pool, 99)),
        "percentile_95_execution_time": float(np.percentile(times_no_pool, 95))
    }

    return results


def output_results_json(results, filename="results/benchmark_results.json"):
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {filename}")


def output_results_csv(results, filename="results/benchmark_results.csv"):
    # Flatten the nested structure for CSV
    flattened_results = []
    for test_type, test_results in results.items():
        for method_results in test_results:
            row = {"test_type": test_type}
            row.update(method_results)
            flattened_results.append(row)

    # Write to CSV
    with open(filename, 'w', newline='') as f:
        if flattened_results:
            writer = csv.DictWriter(f, fieldnames=flattened_results[0].keys())
            writer.writeheader()
            writer.writerows(flattened_results)
    print(f"Results saved to {filename}")


def print_plain_results(results):
    for test_type, test_results in results.items():
        print(f"Test type: {test_type}")
        for result in test_results:
            print(f"  Method: {result['method']}")
            for key, value in result.items():
                if key != "method":
                    print(f"    {key}: {value:.6f}")
            print()


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in {"cpu", "io"}:
        print("Usage: python script.py <cpu|io> [plain|json|csv]")
        sys.exit(1)

    workload = sys.argv[1]
    output_format = sys.argv[2] if len(sys.argv) > 2 else "plain"
    if output_format not in {"plain", "json", "csv"}:
        print(f"Invalid output format: {output_format}")
        sys.exit(1)

    script = SCRIPT_CPU if workload == "cpu" else SCRIPT_IO

    run_cpu_container = partial(
        container_runners.run_container, workload, script)

    # Initialization run (grab docker image if not exists)
    container_runners.initialize()

    # Store results
    all_results = {workload: []}

    # Run tests
    with_pool_results = run_tests_with_pool(run_cpu_container)
    without_pool_results = run_tests_without_pool(run_cpu_container)

    if with_pool_results:
        all_results[workload].append(with_pool_results)
    if without_pool_results:
        all_results[workload].append(without_pool_results)

    # Output based on format
    if output_format == "json":
        output_results_json(all_results)
    elif output_format == "csv":
        output_results_csv(all_results)
    elif output_format == "plain":
        print_plain_results(all_results)


if __name__ == "__main__":
    main()
