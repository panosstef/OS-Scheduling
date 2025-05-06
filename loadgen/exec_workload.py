#!/usr/bin/python3
import time
import argparse
import asyncio
import os
from utils.exec_utils import set_affinities, log_tasks_output, log_total_time
from utils.cpu_monitoring import start_cpu_monitoring, stop_cpu_monitoring
from colorama import Fore, Style

script_dir = os.path.dirname(os.path.realpath(__file__))
workload_file = os.path.join(script_dir, "dataset/workload_dur.txt")

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

	set_affinities(main_cpu, child_cpus)

	start_cpu_monitoring(main_cpu, child_cpus)

	# Read trace file
	tasks = set()
	# Debug values to test IAT
	#time_fired = []
	#iat_values = []  # Store the original IAT values from the file
	start_simulation = time.time()
	with open(workload_file, "r") as f:
		lines = f.readlines()
		for line in lines:
			IAT = float(line.split(" ")[0])
			arg = int(line.split(" ")[1])  # arg is fibonacci N
			await asyncio.sleep(IAT)  # sleep for IAT seconds
			#iat_values.append((IAT, arg))  # Store the original IAT value
			#time_fired.append((time.time(), arg))
			task = asyncio.create_task(launch_command_cpp(arg, child_cpus))
			tasks.add(task)

	task_results = await asyncio.gather(*tasks)
	end_simulation = time.time()

	print(f"{Fore.GREEN}Time elapsed: {end_simulation - start_simulation:.2f} s{Style.RESET_ALL}")

	stop_cpu_monitoring(outputfile, start_simulation, end_simulation)

	await log_tasks_output(task_results, outputfile)

	# Uncomment the following line to debug IAT
	#debug_iat(time_fired, iat_values, start_simulation, outputfile)


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--outputfile", type=str, help="Output file name")
	parser.add_argument("--main-cpu", type=int, default=0,
						help="CPU core for main process")
	parser.add_argument("--child-cpus", type=str, default="1-23",
						help="Comma-separated list of CPU cores for child processes")

	args = parser.parse_args()


	asyncio.run(main(args.outputfile, args.main_cpu, args.child_cpus))
