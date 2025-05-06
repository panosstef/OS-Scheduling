import psutil
import threading
import time
import os
import pandas as pd
from utils.exec_utils import log_dir

monitor_running = False
monitor_thread = None
cores_to_monitor = []
cpu_data = []


def start_cpu_monitoring(main_cpu, child_cpus, interval=0.5):
    global monitor_thread
    monitor_thread = threading.Thread(
        target=monitor_cpu_usage, args=(main_cpu, child_cpus), daemon=True)
    monitor_thread.start()


def stop_cpu_monitoring(outputfile, start_time, end_time):
    global monitor_running, cpu_data, cores_to_monitor
    monitor_running = False
    monitor_thread.join(timeout=2.0)

    # Filter the data to include only the monitored cores, do this after the loop to avoid overhead (in-place)
    cpu_data = [(timestamp, [per_cpu[i] for i in cores_to_monitor])
                for timestamp, per_cpu in cpu_data]

    # Filter the data to include only the time range
    cpu_data = [(timestamp, per_cpu) for timestamp,
                per_cpu in cpu_data if start_time <= timestamp <= end_time]

    output_cpu_utilization(outputfile, cpu_data)


def monitor_cpu_usage(main_cpu, child_cpus, interval=0.5):
    global monitor_running, cpu_data, cores_to_monitor
    monitor_running = True

    # Parse child CPU range
    child_cores = []
    if "-" in child_cpus:
        start, end = map(int, child_cpus.split("-"))
        child_cores = list(range(start, end + 1))
    else:
        child_cores = [int(core) for core in child_cpus.split(",")]
    cores_to_monitor = [main_cpu] + child_cores

    while monitor_running:
        timestamp = time.time()
        per_cpu = psutil.cpu_percent(interval=interval, percpu=True)
        cpu_data.append((timestamp, per_cpu))


def output_cpu_utilization(outputfile, cpu_data):
    df = pd.DataFrame(
        [(ts, *vals) for ts, vals in cpu_data],
        columns=["timestamp"] +
        [f"cpu_{i}" for i in range(len(cpu_data[0][1]))]
    )

    os.makedirs(f"{log_dir}/cpu_util", exist_ok=True)
    df.to_csv(f"{log_dir}/cpu_util/{outputfile}", index=False, mode='a',
              header=not os.path.exists(outputfile))
