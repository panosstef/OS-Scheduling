import time
import container_runners
import numpy as np
import sys
from multiprocessing import Pool
from os import sched_getaffinity
from functools import partial

# Import color codes from container_runners
from container_runners import GREEN, RED, CYAN, YELLOW, RESET

NUM_CONTAINERS = int(sys.argv[2]) if (len(sys.argv) > 2 and int(sys.argv[2])>0) else 100
SCRIPT_CPU = "python -c 'def fib(n): return n if n < 2 else fib(n-1) + fib(n-2); print(fib(30))'"
SCRIPT_IO = (
    "python -c '"
    "with open(\"/tmp/testfile.txt\", \"w\") as f: "
    "    f.write(\"A\" * 10**7); "  # Write a 10MB file
    "with open(\"/tmp/testfile.txt\", \"r\") as f: "
    "    data = f.read(); "
    "print(f\"Read {len(data)} bytes\")'"
)


def main():

    if len(sys.argv) not in {2,3} or sys.argv[1] not in {"cpu", "io"}:
        print(f"{RED}Usage: python script.py <cpu|io>{RESET}")
        sys.exit(1)
    
    workload = sys.argv[1]
    script = SCRIPT_CPU if workload == "cpu" else SCRIPT_IO

    run_cpu_container = partial(
        container_runners.run_container, workload, script)

    # Initialization run (grab docker image if not exists)
    container_runners.initialize()

    print(f"{CYAN}Starting {YELLOW}{NUM_CONTAINERS}{CYAN} containers...{RESET}")
    start_time = time.time()
    with Pool(processes=len(sched_getaffinity(0))) as pool:
        try:
            times = pool.map(run_cpu_container, range(NUM_CONTAINERS))
        except Exception as e:
            print(f"{RED}Error during pool execution: {e}{RESET}")
            return

    end_time = time.time()
    print(f"{GREEN}Total execution time: {YELLOW}{end_time - start_time:.2f}{GREEN} seconds{RESET}")
    print(
        f"{GREEN}Average container execution time: {YELLOW}{sum(times) / NUM_CONTAINERS:.2f}{GREEN} seconds{RESET}")
    print(f"{GREEN}Median container execution time: {YELLOW}{np.median(times):.2f}{GREEN} seconds{RESET}")
    print(f"{GREEN}Standard deviation of container execution time: {YELLOW}{np.std(times):.2f}{GREEN} seconds{RESET}")
    print(f"{GREEN}Max container execution time: {YELLOW}{max(times):.2f}{GREEN} seconds{RESET}")
    print(f"{GREEN}Min container execution time: {YELLOW}{min(times):.2f}{GREEN} seconds{RESET}")
    print(
        f"{GREEN}99th percentile container execution time: {YELLOW}{np.percentile(times,99):.2f}{GREEN} seconds{RESET}")


if __name__ == "__main__":
    main()
