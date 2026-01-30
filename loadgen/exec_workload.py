#!/usr/bin/python3
import time
import argparse
import subprocess
import threading
import queue
import os
import utils.exec_utils as exec_utils
from utils.cpu_monitoring import start_cpu_monitoring, stop_cpu_monitoring
from colorama import Fore, Style

script_dir = os.path.dirname(os.path.realpath(__file__))
workload_file = os.path.join(script_dir, "dataset/workload_dur.txt")
cpu_count = os.cpu_count()

# Thread-safe dictionary: { pid: (arg, request_time, index, Popen_object) }
active_tasks = {}
tasks_lock = threading.Lock()

# Event to signal when the main loop has finished dispatching all tasks
dispatch_complete = threading.Event()

def launcher_worker(task_queue, fifo, sched_ext):
	base_cmd = [f"{script_dir}/payload/launch_function.out"]
	if sched_ext:
		base_cmd = [f"{script_dir}/payload/run_with_sched_ext"] + base_cmd


	cpu_list = ",".join(str(c) for c in range(1, cpu_count))

	while True:
		try:
			item = task_queue.get(timeout=3)
		except queue.Empty:
			return

		if item is None:
			task_queue.task_done()
			break

		arg, index, request_time = item

		try:
			cmd = ["nice", "-n", "15", "taskset", "-c", cpu_list]
			if fifo:
				cmd.extend(["chrt", "-f", "50"])

			full_cmd = cmd + base_cmd + [arg]

			with tasks_lock:
				proc = subprocess.Popen(
					full_cmd,
					stdout=subprocess.PIPE,
					stderr=subprocess.PIPE,
					text=True
				)
				active_tasks[proc.pid] = (arg, request_time, index, proc)

		except Exception as e:
			print(f"Launcher Error: {e}")
		finally:
			task_queue.task_done()

def reaper_thread(results, total_tasks):
	reaped_count = 0

	while reaped_count < total_tasks:
		try:
			# Block until a child process exits.
			pid, status = os.wait()

			task_info = None
			with tasks_lock:
				task_info = active_tasks.pop(pid, None)

			if task_info:
				arg, request_time, index, proc = task_info

				stdout = proc.stdout.read().strip()
				proc.stdout.close()

				# This introduces some jitter as it's not exactly when the process ended,
				# but it's close enough for our purposes.
				return_time = time.time()

				if status != 0:
					if os.WIFEXITED(status) and os.WEXITSTATUS(status) != 0:
						print(f"Process {arg} failed with {os.WEXITSTATUS(status)}")

				results[index] = (stdout, arg, request_time, return_time)
				reaped_count += 1
			else:
				print(f"Reaper Warning: Unknown PID {pid} reaped.")

		except ChildProcessError:
			# os.wait() throws this error if there are no running children.
			# this might happen at the very start (before the first launcher fires)
			# or if there is a massive gap in the workload.
			# We sleep briefly to let the Launchers catch up.
			time.sleep(0.001)
			continue

		except Exception as e:
			print(f"Reaper Error: {e}")
			break

def main(outputfile, time_log=False, cpu_log=False, fifo=False, sched_ext=False, no_log=False):
	os.sched_setaffinity(0, {0})
	os.nice(-15)
	exec_utils.set_ulimit()

	if cpu_log:
		start_cpu_monitoring()

	with open(workload_file, "r") as f:
		lines = f.readlines()

	workload = []
	for i, line in enumerate(lines):
		iat, arg = line.strip().split(" ")
		workload.append((float(iat), str(arg), i))
	workload.reverse()

	results = [None] * len(lines)
	task_queue = queue.Queue()

	# Start reaper (collect finishing tasks)
	reaper = threading.Thread(target=reaper_thread, args=(results, len(lines)))
	reaper.start()

	# Start launchers
	num_launchers = 4
	launchers = []
	print(f"{Fore.GREEN}Starting simulation: 1 Reaper, {num_launchers} Launchers{Style.RESET_ALL}")

	for _ in range(num_launchers):
		t = threading.Thread(target=launcher_worker, args=(task_queue, fifo, sched_ext))
		t.start()
		launchers.append(t)

	start_simulation = time.time()
	next_request_time = start_simulation
	total_tasks = len(lines)
	dispatched = 0

	get_time = time.time
	sleep = time.sleep

	# Main loop: dispatch tasks according to IATs
	while dispatched < total_tasks:
		IAT, arg, index = workload.pop()
		next_request_time += IAT

		now = get_time()

		if now < next_request_time:
			diff = next_request_time - now

			# Sleep in a hybrid manner to reduce CPU usage while maintaining timing accuracy
			if diff > 0.002:
				sleep(diff - 0.001)

			# If still time left, busy-wait
			while get_time() < next_request_time:
				pass

		task_queue.put((arg, index, next_request_time))
		dispatched += 1

	print(f"{Fore.GREEN}Main loop finished dispatching after {time.time()-start_simulation:.2f}s{Style.RESET_ALL}")

	# Signal completion
	dispatch_complete.set()

	# Cleanup launchers
	task_queue.join()
	for _ in range(num_launchers):
		task_queue.put(None)
	for t in launchers:
		t.join()

	print(f"{Fore.GREEN}Waiting for reaper to collect results...{Style.RESET_ALL}")
	reaper.join()

	end_simulation = time.time()
	print(f"{Fore.GREEN}Total time elapsed: {end_simulation - start_simulation:.2f} s{Style.RESET_ALL}")

	if time_log:
		exec_utils.log_total_time(outputfile, end_simulation - start_simulation)

	stop_cpu_monitoring(outputfile, start_simulation, end_simulation)

	if not no_log:
		exec_utils.log_tasks_output(results, outputfile)
	else:
		exec_utils.debug_output_pids(results, outputfile)

if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--outputfile", type=str, help="Output file name")
	parser.add_argument("--time_log", action="store_true", help="Enable time log", default=False)
	parser.add_argument("--cpu_log", action="store_true", help="Enable CPU log", default=False)
	parser.add_argument("--fifo", action="store_true", help="Use FIFO scheduling", default=False)
	parser.add_argument("--sched_ext", action="store_true", help="Use sched_ext scheduler", default=False)
	parser.add_argument("--no_log", action="store_true", help="Disable logging", default=False)
	args = parser.parse_args()

	if (args.fifo): print(f"{Fore.GREEN}Using FIFO scheduling!{Style.RESET_ALL}")
	if (args.sched_ext): print(f"{Fore.GREEN}Using sched_ext scheduler!{Style.RESET_ALL}")

	main(args.outputfile, args.time_log, args.cpu_log, args.fifo, args.sched_ext, args.no_log)
