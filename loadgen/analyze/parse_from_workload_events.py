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
		r'(.+?)-(\d+)\s+\[(\d+)\](?:.*?)?\s+(\d+\.\d+):\s+(\S+):\s+(.*)')

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


def parse_ftrace(file_path):
	print(f"{Fore.GREEN}{Style.BRIGHT}Parsing ftrace file: {file_path}{Style.RESET_ALL}")

	workload_events_dict = defaultdict(list)
	pids_str = set()

	try:
		file_size = os.path.getsize(file_path)

		with open(file_path, 'r') as f:
			# Create progress bar
			with tqdm(total=file_size, unit='B', unit_scale=True,
					  desc="Parsing trace", bar_format='{l_bar}{bar:30}{r_bar}') as pbar:

				for raw_line in f:
					pbar.update(len(raw_line))
					line = raw_line.strip()
					if(line.startswith("PID")):
						pid = int(line.split(":")[1])
					else:
						workload_events_dict[pid].append(parse_event_from_line(line))


	except Exception as e:
		print(f"{Fore.RED}	Error parsing trace file: {e}{Style.RESET_ALL}")
		exit(-1)

	print(f"{Fore.CYAN}{Style.BRIGHT}	Parsed {len(workload_events_dict)} PIDs from the trace file\n{Style.RESET_ALL}")
	return workload_events_dict


def get_workload_times(workload_events):
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

			workload_times[pid] = {
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

def workload_times_out(workload_times, output_file):
	print(f"{Fore.GREEN}{Style.BRIGHT}Writing workload times to CSV{Style.RESET_ALL}")

	# Convert dictionary to DataFrame
	data = []
	for (arg, pid), times in workload_times.items():
		row = {'pid': pid, 'arg': arg}
		row.update(times)
		data.append(row)

	df = pd.DataFrame(data)

	df.to_csv(f"workload_times_{output_file}.csv", index=False)
	print(f"{Fore.CYAN}{Style.BRIGHT}	Workload times written to: workload_times_{output_file}.csv{Style.RESET_ALL}")


def main():
	if len(sys.argv) != 3:
		print("Usage: python parse_trace.py <ftrace_file> <output_file>")
		sys.exit(1)
	file_path = sys.argv[1]
	output_file = sys.argv[2]

	workload_events = parse_ftrace(file_path)
	if not workload_events:
		print(
			f"{Fore.RED}{Style.BRIGHT}No events found in the trace file{Style.RESET_ALL}")
		sys.exit(1)

	# Get times for each pid, each pid has a startup_latency and total_time
	workload_times = get_workload_times(workload_events)

	# Output to csv the times
	workload_times_out(workload_times, output_file)


if __name__ == "__main__":
	main()
