#!/usr/bin/python3
import time
import argparse
import subprocess
import threading
import os
from utils.exec_utils import log_tasks_output, log_total_time, set_ulimit
from utils.cpu_monitoring import start_cpu_monitoring, stop_cpu_monitoring
from colorama import Fore, Style

script_dir = os.path.dirname(os.path.realpath(__file__))
workload_file = os.path.join(script_dir, "dataset/workload_dur.txt")
cpu_count = os.cpu_count()

def launch_command(command, arg, results, index, request_time, preexec_fn=None):
	try:

		os.sched_setaffinity(0, list(range(1, cpu_count)))
		os.nice(15)

		process = subprocess.Popen(
			command + [arg],
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			preexec_fn= preexec_fn)

		stdout, stderr = process.communicate()
		return_time = time.time()

		if process.returncode != 0:
			print(f"Process for arg {arg} exited with code {process.returncode}")
			if stderr:
				print(f"Error: {stderr.decode().strip()}")

		results[index] = (stdout.decode().strip(), arg, request_time, return_time)
	except Exception as e:
		print(f"Exception in task for arg {arg}: {str(e)}")
		results[index] = None

def main(outputfile, time_log=False, cpu_log=False, fifo=False, sched_ext=False, no_log=False):
	os.sched_setaffinity(0, {0})  # Set CPU affinity to CPU 0
	os.nice(-15)
	set_ulimit()

	command = [f"{script_dir}/payload/launch_function.out"]

	if fifo:
		preexec_fn = lambda: os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(50))
	elif sched_ext:
		preexec_fn = None
		command = [f"{script_dir}/payload/run_with_sched_ext"] + command
	else:
		preexec_fn = None

	if cpu_log:
		start_cpu_monitoring()

	with open(workload_file, "r") as f:
		lines = f.readlines()

	threads = []
	results = [None] * len(lines)
	iats_wargs = [(float(iat), str(arg)) for iat, arg in (line.strip().split(" ") for line in lines)]
	iats_wargs.reverse()

	start_simulation = time.time()
	next_request_time = start_simulation
	print(f"{Fore.GREEN}Starting simulation{Style.RESET_ALL}")

	for i in range(len(lines)):
		IAT, arg = iats_wargs.pop()
		next_request_time += IAT

		# Sleep until it's time for the next request, accounting for overhead
		current_time = time.time()
		sleep_duration = next_request_time - current_time

		if sleep_duration > 0:
			time.sleep(sleep_duration)

		t = threading.Thread(target=launch_command, args=(command, arg, results, i, next_request_time, preexec_fn))
		t.start()
		threads.append(t)

	print(f"{Fore.GREEN}Main loop finished after {time.time()-start_simulation}{Style.RESET_ALL}")

	for t in threads:
		t.join()

	end_simulation = time.time()

	print(f"{Fore.GREEN}Time elapsed: {end_simulation - start_simulation:.2f} s{Style.RESET_ALL}")
	if time_log:
		log_total_time(outputfile, end_simulation - start_simulation)

	stop_cpu_monitoring(outputfile, start_simulation, end_simulation)

	if not no_log:
		log_tasks_output(results, outputfile)

if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--outputfile", type=str, help="Output file name")
	parser.add_argument("--time_log", action="store_true", help="Enable time log", default=False)
	parser.add_argument("--cpu_log", action="store_true", help="Enable CPU log", default=False)
	parser.add_argument("--fifo", action="store_true", help="Use FIFO scheduling", default=False)
	parser.add_argument("--sched_ext", action="store_true", help="Use sched_ext scheduler", default=False)
	parser.add_argument("--no_log", action="store_true", help="Disable logging", default=False)
	args = parser.parse_args()

	if (args.fifo):
		print(f"{Fore.GREEN}Using FIFO scheduling!{Style.RESET_ALL}")

	if (args.sched_ext):
		print(f"{Fore.GREEN}Using sched_ext scheduler!{Style.RESET_ALL}")

	main(args.outputfile, args.time_log, args.cpu_log, args.fifo, args.sched_ext, args.no_log)