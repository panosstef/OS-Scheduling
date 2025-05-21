#!/usr/bin/python3
import time
import argparse
import subprocess
import threading
import os
from utils.exec_utils import set_affinities, log_tasks_output, log_total_time
from utils.cpu_monitoring import start_cpu_monitoring, stop_cpu_monitoring
from colorama import Fore, Style

script_dir = os.path.dirname(os.path.realpath(__file__))
workload_file = os.path.join(script_dir, "dataset/workload_dur.txt")

# Task launcher using Popen
def launch_command_cpp(arg, results, index):
	command = f"{script_dir}/payload/launch_function.out {arg}"
	try:
		process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		stdout, stderr = process.communicate()

		if process.returncode != 0:
			print(f"Process for arg {arg} exited with code {process.returncode}")
			if stderr:
				print(f"Error: {stderr.decode().strip()}")

		results[index] = stdout.decode().strip()
	except Exception as e:
		print(f"Exception in task for arg {arg}: {str(e)}")
		results[index] = None

def main(outputfile, cpu_log = False):
	# set_affinities(main_cpu, child_cpus)
	if cpu_log:
		start_cpu_monitoring()

	threads = []
	results = []

	with open(workload_file, "r") as f:
		lines = f.readlines()

	start_simulation = time.time()

	for i, line in enumerate(lines):
		IAT = float(line.split(" ")[0])
		arg = int(line.split(" ")[1])

		time.sleep(IAT)

		results.append(None)  # Placeholder for thread result
		t = threading.Thread(target=launch_command_cpp, args=(arg, results, i))
		t.start()
		threads.append(t)

	for t in threads:
		t.join()

	end_simulation = time.time()

	print(f"{Fore.GREEN}Time elapsed: {end_simulation - start_simulation:.2f} s{Style.RESET_ALL}")

	stop_cpu_monitoring(outputfile, start_simulation, end_simulation)
	log_tasks_output(results, outputfile)

if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--outputfile", type=str, help="Output file name")
	parser.add_argument("--cpu_log", action="store_true", help="Enable CPU log", default=False)
	args = parser.parse_args()

	main(args.outputfile, args.cpu_log)
