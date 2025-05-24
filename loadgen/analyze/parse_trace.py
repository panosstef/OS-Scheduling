#!/usr/bin/env python3
import sys
import re
import os
import pandas as pd

from colorama import Fore, Style
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Any
from tqdm import tqdm  # Add this import

# Get current working directory
cwd = os.path.dirname(os.path.realpath(__file__))


@dataclass
class TraceEvent:
	process: str
	pid: int
	cpu: int
	timestamp: float
	event_type: str
	details: List[Dict[str, Any]]
	raw_line: str


def parse_event_from_line(line):
	# Regex pattern for parsing ftrace lines
	# Format: process-pid [cpu]timestamp: event_type: details
	# e.g trace-cmd-3548  [000]  4896.102217: task_rename:          pid=3548 oldcomm=trace-cmd newcomm=exec_workload.p oom_score_adj=0
	trace_pattern = re.compile(
		r'(.+?)-(\d+)\s+\[(\d+)\]\s+(\d+\.\d+):\s+(\S+):\s+(.*)')

	match = trace_pattern.match(line)
	if match:
		process, pid, cpu, timestamp, event_type, details_str = match.groups()

		event = TraceEvent(
			process=process,
			pid=int(pid),
			cpu=int(cpu),
			timestamp=float(timestamp),
			event_type=event_type,
			details=details_str.strip(),
			raw_line=line.rstrip()
		)

		return event

	else:
		print(
			f"{Fore.RED}{Style.BRIGHT}	Failed to match line: {line}{Style.RESET_ALL}")
		exit(-1)


def parse_ftrace(file_path, pids: set):
	print(f"{Fore.GREEN}{Style.BRIGHT}Parsing ftrace file: {file_path}{Style.RESET_ALL}")

	workload_events_dict = defaultdict(list)
	pids_str = {str(pid) for pid in pids}  # Convert all PIDs to strings once

	try:
		file_size = os.path.getsize(file_path)

		with open(file_path, 'r') as f:
			# Remove the first comment or #ncpus line
			_ = f.readline()

			# Create progress bar
			with tqdm(total=file_size, unit='B', unit_scale=True,
					  desc="Parsing trace", bar_format='{l_bar}{bar:30}{r_bar}') as pbar:

				for raw_line in f:
					pbar.update(len(raw_line))
					line = raw_line.strip()

					for pid_str in pids_str:
						if pid_str in line:
							event = parse_event_from_line(line)
							# Border case where the pid is part of the digits in timestamp
							if pid_str not in str(event.pid) and pid_str not in str(event.details):
								continue
							else:
								workload_events_dict[int(
									pid_str)].append(event)

							# Check if the event is sched_process_exit, if so remove the pid from the set
							if event.event_type == "sched_process_exit" and f"pid={pid_str}" in event.details:
								# Remove PID from set once found
								pids_str.remove(pid_str)
								break

	except Exception as e:
		print(f"{Fore.RED}	Error parsing trace file: {e}{Style.RESET_ALL}")
		exit(-1)

	print(f"{Fore.CYAN}{Style.BRIGHT}	Parsed {len(workload_events_dict)} PIDs from the trace file\n{Style.RESET_ALL}")
	return workload_events_dict


def check_all_pids(workload_events_keys, pids):
	print(f"{Fore.GREEN}{Style.BRIGHT}Checking all pids in the workload events{Style.RESET_ALL}")
	for pid in workload_events_keys:
		try:
			pids.remove(pid)
		except KeyError:
			print(
				f"{Fore.RED}{Style.BRIGHT}	PID {pid} not found in the workload events{Style.RESET_ALL}")
			exit(-1)

	if pids:
		print(
			f"{Fore.RED}{Style.BRIGHT}	PIDs not found in the workload events: {pids}{Style.RESET_ALL}")
		exit(-1)

	print(f"{Fore.CYAN}{Style.BRIGHT}	All PIDs found in the workload events\n{Style.RESET_ALL}")


def pids_ftoset(pid_file):
	# Read the pid file and convert to a set of integers
	print(f"{Fore.GREEN}{Style.BRIGHT}Parsing PID file: {pid_file}{Style.RESET_ALL}")
	pids = set()
	try:
		with open(pid_file, 'r') as f:
			for line in f:
				pid, arg = line.strip().split()
				if pid and arg and pid.isdigit() and arg.isdigit():
					pids.add((int(arg), int(pid)))
				else:
					raise ValueError(
						f"{Fore.RED}{Style.BRIGHT}Invalid line in PID file: {line}{Style.RESET_ALL}")
	except Exception as e:
		print(f"{Fore.RED}	Error reading PID file: {e}{Style.RESET_ALL}")
		exit(-1)

	print(f"{Fore.CYAN}{Style.BRIGHT}	Workload PIDs found: {len(pids)}\n{Style.RESET_ALL}")
	return pids


def get_workload_times(workload_events, pids_wargs):
	print(f"{Fore.GREEN}{Style.BRIGHT}Getting workload times{Style.RESET_ALL}")
	workload_times = {}

	for pid, events in workload_events.items():
		try:
			start_time = None
			first_scheduled_time = None
			exit_time = None

			for event in events:
				if start_time is None and event.event_type == "sched_process_fork" and f"child_pid={pid}" in event.details:
					start_time = event.timestamp
					continue

				if (start_time is not None and first_scheduled_time is None and
						event.event_type == "sched_switch" and f"next_pid={pid}" in event.details):
					first_scheduled_time = event.timestamp
					continue

				if first_scheduled_time is not None and event.event_type == "sched_process_exit" and f"pid={pid}" in event.details:
					exit_time = event.timestamp
					break

			startup_latency = first_scheduled_time - start_time

			# Check that all time are not none and that start<exit and latency <start-exit
			if None in (start_time, first_scheduled_time, exit_time):
				print(
					f"{Fore.RED}{Style.BRIGHT}Error: Missing times for PID {pid}{Style.RESET_ALL}")
				print(
					f"{Fore.RED}{Style.BRIGHT}{start_time} {first_scheduled_time	} {exit_time}{Style.RESET_ALL}")
				print(events)
				exit(-1)
			if start_time > exit_time or startup_latency > (exit_time - start_time):
				print(
					f"{Fore.RED}{Style.BRIGHT}Error: Invalid times for PID {pid}: {start_time} {startup_latency} {exit_time}{Style.RESET_ALL}")
				exit(-1)

			#Find the arguments of the workload
			arg = next(
				(arg for arg, pid_arg in pids_wargs if pid_arg == pid), None)
			if arg is None:
				print(
					f"{Fore.RED}{Style.BRIGHT}Error: PID {pid} not found in the workload arguments{Style.RESET_ALL}")
				exit(-1)

			workload_times[(arg, pid)] = {
				"start_time": start_time,
				"startup_latency": startup_latency,
				"exit_time": exit_time
			}
		except Exception as e:
			print(
				f"{Fore.RED}{Style.BRIGHT}Error processing PID {pid}: {e}{Style.RESET_ALL}")
			print(events)
			exit(-1)

	print(
		f"{Fore.CYAN}{Style.BRIGHT}	Parsed workload times for {len(workload_times)} pids\n{Style.RESET_ALL}")
	return workload_times


def workload_events_out(workload_events):
	output_file = cwd + "/workload_events.out"
	print(f"{Fore.GREEN}{Style.BRIGHT}Writing workload events to: {output_file}{Style.RESET_ALL}")
	try:
		with open(output_file, 'w') as f:
			for pid, events in workload_events.items():
				f.write(f"PID: {pid}\n")
				for event in events:
					f.write(f"\t{event.raw_line}\n")
	except Exception as e:
		print(f"{Fore.RED}	Error writing workload events: {e}{Style.RESET_ALL}")
		exit(-1)

	print(f"{Fore.CYAN}{Style.BRIGHT}	Workload events written to: {output_file}\n{Style.RESET_ALL}")


def workload_times_out(workload_times, output_file):
	print(f"{Fore.GREEN}{Style.BRIGHT}Writing workload times to CSV{Style.RESET_ALL}")

	# Convert dictionary to DataFrame
	data = []
	for (arg, pid), times in workload_times.items():
		row = {'pid': pid, 'arg': arg}
		row.update(times)
		data.append(row)

	df = pd.DataFrame(data)

	df.to_csv(
		f"{os.getcwd()}/tmp/workload_times_{output_file}.csv", index=False)
	print(f"{Fore.CYAN}{Style.BRIGHT}	Workload times written to: workload_times_{output_file}.csv{Style.RESET_ALL}")


def main():
	if len(sys.argv) != 4:
		print("Usage: python parse_trace.py <ftrace_file> <pid_file> <output_file>")
		sys.exit(1)
	file_path = sys.argv[1]
	pid_file = sys.argv[2]
	output_file = sys.argv[3]

	pids_wargs = pids_ftoset(pid_file)
	pids: set = {pid for _, pid in pids_wargs}

	workload_events = parse_ftrace(file_path, pids)
	if not workload_events:
		print(
			f"{Fore.RED}{Style.BRIGHT}No events found in the trace file{Style.RESET_ALL}")
		sys.exit(1)

	# Check found events for all pids
	check_all_pids(workload_events.keys(), pids)

	# Print the workload events to a file
	workload_events_out(workload_events)

	# Get times for each pid, each pid has a startup_latency and total_time
	workload_times = get_workload_times(workload_events, pids_wargs)

	# Output to csv the times
	workload_times_out(workload_times, output_file)


if __name__ == "__main__":
	main()
