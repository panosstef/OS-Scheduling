import psutil
import threading
import time
import pandas as pd

monitor_running = False
monitor_thread = None
cores_to_monitor = []
cpu_data = []


def start_cpu_monitoring(interval=0.2):
	global monitor_thread
	monitor_thread = threading.Thread(
		target=monitor_cpu_usage, args=[interval], daemon=True)
	monitor_thread.start()


def stop_cpu_monitoring(outputfile, start_time, end_time):
	global monitor_running, cpu_data
	monitor_running = False
	if not monitor_thread:
		return
	monitor_thread.join(timeout=2.0)

	# Filter the data to include only the time range
	cpu_data = [(timestamp, per_cpu) for timestamp,
				per_cpu in cpu_data if start_time <= timestamp <= end_time]

	output_cpu_utilization(outputfile, cpu_data)


def monitor_cpu_usage(interval):
	global monitor_running, cpu_data, cores_to_monitor
	monitor_running = True

	while monitor_running:
		timestamp = time.time()
		per_cpu = psutil.cpu_percent(interval=interval, percpu=True)
		cpu_data.append((timestamp, per_cpu))


def output_cpu_utilization(outputfile, cpu_data):
	#Duration of the execution was short enough that no data was collected
	if not cpu_data:
		print("No CPU data collected.")
		return

	df = pd.DataFrame(
		[(ts, *vals) for ts, vals in cpu_data],
		columns=["timestamp"] +
		[f"cpu_{i}" for i in range(len(cpu_data[0][1]))]
	)

	df.to_csv(f"{outputfile}_cpu_util.csv", index=False, mode='a')
