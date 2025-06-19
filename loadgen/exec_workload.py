#!/usr/bin/python3
import time
import argparse
import subprocess
import threading
import os
from utils.exec_utils import log_tasks_output, log_total_time, add_to_cgroup, set_ulimit, debug_iat
from utils.cpu_monitoring import start_cpu_monitoring, stop_cpu_monitoring
from colorama import Fore, Style

script_dir = os.path.dirname(os.path.realpath(__file__))
workload_file = os.path.join(script_dir, "dataset/workload_dur.txt")

def add_process_to_workload_cgroup(pid, cgroup_path):
	"""Add a process to the workload cgroup"""
	if cgroup_path:
		try:
			with open(os.path.join(cgroup_path, "cgroup.procs"), "w") as f:
				f.write(str(pid))
		except Exception as e:
			print(f"Warning: Could not add process {pid} to workload cgroup: {e}")

def launch_command(command, arg, results, index, request_time, workload_cgroup_path=None):
	try:
		# Create preexec function to add process to cgroup before execution
		preexec_fn = None
		if workload_cgroup_path:
			preexec_fn = lambda: add_process_to_workload_cgroup(os.getpid(), workload_cgroup_path)

		process = subprocess.Popen(
			command + [arg],
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			preexec_fn=preexec_fn)

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

def main(outputfile, time_log=False, cpu_log=False, debug_interarrivals=False, fifo=False, no_log=False):
	add_to_cgroup()
	set_ulimit()

	workload_cgroup_path = "/sys/fs/cgroup/loadgen/workload"

	if fifo:
		command = ["chrt", "-f", "50", f"{script_dir}/payload/launch_function.out"]
	else:
		command = [f"{script_dir}/payload/launch_function.out"]

	if cpu_log:
		start_cpu_monitoring()

	if debug_interarrivals:
		time_started = []

	with open(workload_file, "r") as f:
		lines = f.readlines()

	threads = []
	results = [None] * len(lines)
	len_lines = len(lines)
	iats_wargs = [(float(iat), str(arg)) for iat, arg in (line.strip().split(" ") for line in lines)]
	iats_wargs.reverse()

	start_simulation = time.time()

	for i in range(len_lines):
		IAT, arg = iats_wargs.pop()
		time.sleep(IAT)
		request_time = time.time()
		t = threading.Thread(target=launch_command, args=(command, arg, results, i, request_time, workload_cgroup_path))
		t.start()
		threads.append(t)

		if debug_interarrivals:
			time_started.append(request_time)

	for t in threads:
		t.join()

	end_simulation = time.time()

	print(f"{Fore.GREEN}Time elapsed: {end_simulation - start_simulation:.2f} s{Style.RESET_ALL}")
	if time_log:
		log_total_time(outputfile, end_simulation - start_simulation)

	if debug_interarrivals:
		with open(workload_file, "r") as f:
			lines = f.readlines()
			debug_iat(time_started, [float(line.split(" ")[0]) for line in lines], start_simulation, outputfile)

	stop_cpu_monitoring(outputfile, start_simulation, end_simulation)

	if not no_log:
		log_tasks_output(results, outputfile)

if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--outputfile", type=str, help="Output file name")
	parser.add_argument("--time_log", action="store_true", help="Enable time log", default=False)
	parser.add_argument("--cpu_log", action="store_true", help="Enable CPU log", default=False)
	parser.add_argument("--debug_iat", action="store_true", help="Enable debug mode", default=False)
	parser.add_argument("--fifo", action="store_true", help="Use FIFO scheduling", default=False)
	parser.add_argument("--no_log", action="store_true", help="Disable logging", default=False)
	args = parser.parse_args()

	if(args.fifo):
		print(f"{Fore.GREEN}Using FIFO scheduling!{Style.RESET_ALL}")

	main(args.outputfile, args.time_log, args.cpu_log, args.debug_iat, args.fifo, args.no_log)