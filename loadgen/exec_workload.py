#!/usr/bin/python3
import time
import argparse
import asyncio
import psutil
import socket
import os
from colorama import Fore, Style

# Get the current directory of the script
script_dir = os.path.dirname(os.path.realpath(__file__))

# Modify paths to be relative to the script directory
workload_file = os.path.join(script_dir, "dataset/workload_dur.txt")
log_dir = os.path.join(script_dir, "log")

# Ensure the log directory exists
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

	# Write the IAT to a file
	with open(f"{log_dir}/{socket.gethostname()}_{outputfile}_IAT.txt", "w") as f:
		for i in range(0, len(interarrival_times)):
			f.write(f"{interarrival_times[i][0]} {interarrival_times[i][1]}\n")

	# Get % difference between workload IAT and actual IAT
	with open(f"{log_dir}/{socket.gethostname()}_{outputfile}_IAT_diff.txt", "w") as f:
		for i in range(0, len(interarrival_times)):
			if iat_values[i][0] == 0:
				continue
			else:
				f.write(
					f"{interarrival_times[i][1]}: {(interarrival_times[i][0] - iat_values[i][0])/iat_values[i][0]}%\n")


async def log_tasks_output(task_results, outputfile):
	# Create a directory for the tasks pids if it doesn't exist
	log_dir_pids = f"{log_dir}/tasks_pids/"
	os.makedirs(log_dir_pids, exist_ok=True)
	log_file_pids = f"{log_dir_pids}/{socket.gethostname()}_{outputfile}_pids.txt"
	# parse pids from each line into a se
	# output is e.g pid: 3300 fib(36): 24157817
	task_results = [output.split(" ")[1] for output in task_results]

	# Write the pids to the file

	with open(log_file_pids, "w") as f:
		f.write("\n".join([pid for pid in task_results])+"\n")
	print(f"{Fore.CYAN}Run {len(task_results)} tasks. Pids is saved in {log_file_pids}{Style.RESET_ALL}")

# Runner
async def launch_command_cpp(arg, child_cpus):
	command = f"taskset -c {child_cpus} {script_dir}/payload/launch_function.out {arg}"
	try:
		process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
		stdout, stderr = await process.communicate()

		if process.returncode != 0:
			print(
				f"Process for arg {arg} exited with code {process.returncode}")
			if stderr:
				print(f"Error: {stderr.decode().strip()}")

		return stdout.decode().strip()
	except Exception as e:
		print(f"Exception in task for arg {arg}: {str(e)}")
		raise

# Launch the C++ fibonacci function according to the trace file IAT
async def main(outputfile, main_cpu, child_cpus):
	# Set CPU affinity for the main Python process
	set_affinities(main_cpu, child_cpus)

	# Read trace file
	tasks = set()
	# Debug values to test IAT
	# time_fired = []
	# iat_values = []  # Store the original IAT values from the file
	start_simulation = time.time()
	with open(workload_file, "r") as f:
		lines = f.readlines()
		for line in lines:
			IAT = float(line.split(" ")[0])
			arg = int(line.split(" ")[1])  # arg is fibonacci N
			await asyncio.sleep(IAT)  # sleep for IAT seconds
			# iat_values.append((IAT, arg))  # Store the original IAT value
			# time_fired.append((time.time(), arg))
			task = asyncio.create_task(launch_command_cpp(arg, child_cpus))
			tasks.add(task)

	# Wait for all tasks to complete
	task_results = await asyncio.gather(*tasks)

	end_simulation = time.time()
	print(f"{Fore.GREEN}Time elapsed: {end_simulation - start_simulation:.2f} s{Style.RESET_ALL}")

	# log the output for each task
	await log_tasks_output(task_results, outputfile)

	# log the results to the output file
	if outputfile is not None:
		with open(f"{log_dir}/{socket.gethostname()}_{outputfile}.txt", "a") as f:
			f.write(f"time elapsed: {end_simulation - start_simulation} s\n")

	# debug_iat(time_fired, iat_values, start_simulation, outputfile)


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--outputfile", type=str, help="Output file name")
	parser.add_argument("--main-cpu", type=int, default=0,
						help="CPU core for main process")
	parser.add_argument("--child-cpus", type=str, default="1-23",
						help="Comma-separated list of CPU cores for child processes")

	args = parser.parse_args()
	main_cpu = args.main_cpu
	child_cpus = args.child_cpus

	asyncio.run(main(args.outputfile, main_cpu, child_cpus))
