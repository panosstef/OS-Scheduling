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

def launch_command(command, arg, results, index):
	try:
		process = subprocess.Popen(
			command + [arg], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		stdout, stderr = process.communicate()

		if process.returncode != 0:
			print(f"Process for arg {arg} exited with code {process.returncode}")
			if stderr:
				print(f"Error: {stderr.decode().strip()}")

		results[index] = stdout.decode().strip()
	except Exception as e:
		print(f"Exception in task for arg {arg}: {str(e)}")
		results[index] = None

def main(outputfile, time_log=False, cpu_log=False, debug_interarrivals=False, fifo=False, no_log=False):
	add_to_cgroup()
	set_ulimit()

	if fifo:
		command = f"chrt -f 50 {script_dir}/payload/launch_function.out".split()
	else:
		command = f"{script_dir}/payload/launch_function.out"

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

	if debug_interarrivals:  # for minimal runtime overhead
		for i in range(len_lines):
			IAT, arg = iats_wargs.pop()
			time.sleep(IAT)
			time_started.append((time.time(), arg))
			t = threading.Thread(target=launch_command, args=(command, arg, results, i))
			t.start()
			threads.append(t)
	else:
		for i in range(len_lines):
			IAT, arg = iats_wargs.pop()
			time.sleep(IAT)
			t = threading.Thread(target=launch_command, args=(command, arg, results, i))
			t.start()
			threads.append(t)

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

	main(args.outputfile, args.time_log, args.cpu_log, args.debug_iat, args.fifo, args.no_log)
