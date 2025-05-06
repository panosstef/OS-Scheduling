import psutil
import os
import __main__
from colorama import Fore, Style

script_dir = os.path.dirname(os.path.realpath(__main__.__file__))
log_dir = os.path.join(script_dir, "log")
os.makedirs(log_dir, exist_ok=True)

def set_affinities(main_cpu, child_cpus):
	p = psutil.Process()
	p.cpu_affinity([main_cpu])
	print(f"Main process pinned to CPU {main_cpu}")
	print(f"Child processes will be pinned to CPUs: {child_cpus}")

def debug_iat(time_fired, iat_values, start_simulation, outputfile):
	# Calculate IAT
	interarrival_times = []
	interarrival_times.append(
		(time_fired[0][0] - start_simulation, time_fired[0][1]))
	for i in range(1, len(time_fired)):
		interarrival_times.append(
			(time_fired[i][0] - time_fired[i-1][0], time_fired[i][1]))

	# Get % difference between workload IAT and actual IAT
	with open(f"{log_dir}/{outputfile}_IAT_diff.txt", "w") as f:
		for i in range(0, len(interarrival_times)):
			if iat_values[i][0] == 0:
				continue
			else:
				f.write(
					f"{interarrival_times[i][1]}: {(interarrival_times[i][0] - iat_values[i][0])/iat_values[i][0]}%\n")

async def log_tasks_output(task_results, outputfile):

	# Create a directory for the tasks pids if it doesn't exist
	log_dir_pids = f"{script_dir}/tmp"
	os.makedirs(log_dir_pids, exist_ok=True)
	log_file_pids = f"{log_dir_pids}/{outputfile}_pids.txt"
	# parse pids from each line into a se
	# output is e.g pid: 3300 fib(36): 24157817
	task_results = [output.split(" ")[1] for output in task_results]

	# Write the pids to the file
	with open(log_file_pids, "w") as f:
		f.write("\n".join([pid for pid in task_results])+"\n")
	print(f"{Fore.CYAN}Run {len(task_results)} tasks. Pids saved in {log_file_pids}{Style.RESET_ALL}")

def log_total_time(start_simulation, end_simulation, outputfile):
	with open(f"{log_dir}/total_time.txt", "a") as f:
			f.write(f"{outputfile}: {end_simulation - start_simulation:.2f} s\n")

