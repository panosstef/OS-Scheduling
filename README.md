# OS-Scheduling

Repo for code in thesis regarding OS schedulers (Linux - CFS - EEVDF). Main evaluation on serverless workloads. 

This repository introduces `scx_serverless`, a custom scheduler built upon the `sched_ext` framework. The scheduler identifies and prioritizes short-lived FaaS tasks through a workload-aware policy, allowing them to run to completion with minimal interruptions (`/sched_ext`). 

To evaluate the scheduler under CPU contention, the repository includes a FaaS workload simulator and an automated benchmarking pipeline driven by `ftrace` and `perf` (`/loadgen`) .

## Repository Structure

The codebase is divided into two primary domains: the eBPF scheduling logic and the FaaS benchmarking pipeline.

### `sched_ext/` (Custom Scheduler)
* **`scx_serverless.c`**: The userspace implementation of the `scx_serverless` scheduler. It loads the eBPF scheduler into the kernel, manages eBPF maps, and provides timeslices back to the kernel.
* **`scx_serverless.bpf.c`**: The eBPF code containing the core logic for scheduling decisions via a collection of eBPF callbacks.

### `loadgen/` (Workload Simulator & Benchmarking)

#### 1. FaaS Simulator & Dataset Generation
The workload generator synthesizes reproducible, scalable scenarios derived from the Microsoft Azure Functions trace.
* **`calibrate.py`**: Hardware calibration script that collects execution times of the Fibonacci payload across different input parameters to map function parameters to execution times.
* **`dataset/gen_workload.py`**: Workload generator that samples the Azure Functions trace and maps execution durations to the Fibonacci benchmark.
* **`dataset/workload_dur.txt`**: The generated workload trace containing interarrival times and Fibonacci arguments.
* **`exec_workload.py`**: The main execution simulator. It reads the generated trace and dispatches function invocations according to the specified interarrival times, modeling a FaaS environment under CPU contention.
* **`payload/launch_function.cc`**: A C++ CPU-heavy payload that computes a Fibonacci number and prints the process PID and result to `stdout`.
* **`run_with_sched_ext.c`**: A C helper program that uses `sched_setattr` to isolate and execute specific workload items under the `SCHED_EXT` scheduling class.

#### 2. Benchmarking Pipeline
The pipeline automates experiments across varying workload sizes and scheduling environments (CFS, EEVDF, FIFO, SCHED_EXT).
* **`run_all.sh`**: Top-level experiment wrapper. It iterates over different workload dataset downscale sizes (300, 500, 700, 1700) and calls the experiment runner for each.
* **`run_experiment.sh`**: Sets up the environment limits (e.g., `ulimit` for file descriptors) and sequentially triggers the `ftrace` and `perf` benchmarking variants.
* **`runners/run_experiment_ftrace.sh`**: Wraps the workload execution using `trace-cmd` to capture context switches, migrations, and process lifecycle events.
* **`runners/run_experiment_perf.sh`**: Wraps the execution using `perf sched record` to capture detailed scheduling delay distributions and CPU-execution bursts.

#### 3. Trace Analysis (`loadgen/analyze/`)
* **`parse_trace.py`**: Parses the ASCII output of `trace-cmd` to extract per-task lifecycle metrics (e.g., startup latency, execution time, total migrations).
* **`parse_perf/*.py`**: A collection of scripts that parse `perf sched latency` and `perf sched timehist` reports, aggregating metrics like wait times, run times, and maximum scheduling delays into CSV formats.

## Acknowledgments
*Some code in the workload generator is adapted from [ZhaoNeil/hybrid-scheduler](https://github.com/ZhaoNeil/hybrid-scheduler/tree/main).* Uses the 2019 Azure Functions trace dataset.
