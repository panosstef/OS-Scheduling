import psutil
import os
import subprocess
import __main__
import pandas as pd
from colorama import Fore, Style

script_dir = os.path.dirname(os.path.realpath(__main__.__file__))
log_dir = os.path.join(script_dir, "log")
os.makedirs(log_dir, exist_ok=True)


def add_to_cgroup():
	cgroup_procs_path = "/sys/fs/cgroup/loadgen/orchestrator/cgroup.procs"
	try:
		with open(cgroup_procs_path, "w") as f:
			f.write(str(os.getpid()))
	except FileNotFoundError:
		subprocess.run([f"{script_dir}/cpu_isolation/setup_cpu_isolation.sh"], check=True)

def set_ulimit():
	try:
		psutil.Process(os.getpid()).rlimit(psutil.RLIMIT_NOFILE, (65536, 65536))
	except psutil.Error as e:
		print(f"{Fore.RED}Failed to set ulimit: {e}{Style.RESET_ALL}")
		exit(-1)

def debug_iat(time_fired, iat_values, start_simulation, outputfile):
	# Calculate IAT
	interarrival_times = []
	interarrival_times.append(
		(time_fired[0][0] - start_simulation, time_fired[0][1]))
	for i in range(1, len(time_fired)):
		interarrival_times.append(
			(time_fired[i][0] - time_fired[i-1][0], time_fired[i][1]))

	# Output the actual IAT times
	with open(f"{outputfile}_IAT.txt", "w") as f:
		for i in range(0, len(interarrival_times)):
			f.write(
				f"{interarrival_times[i][1]}: {interarrival_times[i][0]}\n")

	# Get % difference between workload IAT and actual IAT
	with open(f"{outputfile}_IAT_diff.txt", "w") as f:
		for i in range(0, len(interarrival_times)):
			if iat_values[i] == 0:
				f.write(
					f"{interarrival_times[i][1]}: {interarrival_times[i][0]} (should be 0)\n")
			else:
				f.write(
					f"{interarrival_times[i][1]}: {(interarrival_times[i][0] - iat_values[i])/iat_values[i]}%\n")

def log_tasks_output(task_results, outputfile):
	# Extract PID and argument from each output line
	lines = []
	timing_data = []

	for (output, arg, request_time, return_time) in task_results:
		pid = output.split()[0]
		lines.append(f"{pid} {arg}")

		# For timings output
		duration = return_time - request_time
		timing_data.append({
			'pid': pid,
			'arg': arg,
			'request_time': request_time,
			'return_time': return_time,
			'duration': duration
		})

	# Write to file pids with arguments
	with open(f"{outputfile}_pids.txt", "w") as f:
		f.write("\n".join(lines) + "\n")
	print(f"{Fore.CYAN}Run {len(lines)} tasks. Pids saved in {outputfile}_pids.txt{Style.RESET_ALL}")

	#Another file add timing data as cs
	timing_df = pd.DataFrame(timing_data)
	timing_df.to_csv(f"{outputfile}_timings.csv" ,index=False)

def log_total_time(outputfile, total_time):
	with open(f"{os.getcwd()}/gen_stats.txt", "a") as f:
		f.write(f"{outputfile}: {total_time:.2f} s\n")

def debug_output_pids(task_results, outputfile):
	# Extract PID and argument from each output line
	lines = []

	for (output, arg, _, _) in task_results:
		pid = output.split()[0]
		lines.append(f"{pid} {arg}")

	# Write to file pids with arguments
	with open(f"{outputfile}_pids.txt", "w") as f:
		f.write("\n".join(lines) + "\n")
	print(f"{Fore.CYAN}Run {len(lines)} tasks. Pids saved in {outputfile}_pids.txt{Style.RESET_ALL}")