#!/usr/bin/env python3
import sys
import re
import os
from colorama import Fore, Style
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Any

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
		r'(\S+)-(\d+)\s+\[(\d+)\]\s+(\d+\.\d+):\s+(\S+):\s+(.*)')

	match = trace_pattern.match(line.strip())
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
		with open(file_path, 'r') as f:
			# Remove the first comment or #ncpus line
			_ = f.readline()

			for line in f:
				for pid_str in pids_str:
					if str(pid) in line:

						event = parse_event_from_line(line)
						pid = int(pid_str)
						workload_events_dict[pid].append(event)

					else:
						continue

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
				line = line.strip()
				if line and line.isdigit():
					pids.add(int(line))
				else:
					raise ValueError(
						f"{Fore.RED}{Style.BRIGHT}Invalid line in PID file: {line}{Style.RESET_ALL}")
	except Exception as e:
		print(f"{Fore.REtimestampD}	Error reading PID file: {e}{Style.RESET_ALL}")
		exit(-1)

	print(f"{Fore.CYAN}{Style.BRIGHT}	Workdload PID found: {len(pids)}\n{Style.RESET_ALL}")
	return pids


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


def main():
	if len(sys.argv) != 3:
		print("Usage: python parse_trace.py <ftrace_file> <pid_file>")
		sys.exit(1)
	file_path = sys.argv[1]
	pid_file = sys.argv[2]

	pids: set = pids_ftoset(pid_file)

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
	workload_times = {}

	for pid, events in workload_events.items():

		start_time = None
		startup_latency = None
		exit_time = None


		start_time = next(
		(event.timestamp for event in events
			if event.event_type == "sched_process_fork"
			and f"child_pid={pid}" in event.details),
		None
		)

		exit_time = next(
		(event.timestamp for event in events
			if event.event_type == "sched_process_exit"
			and f"pid={pid}" in event.details),
		None
		)

		first_scheduled_details = next(
		(event.details for event in events
			if event.event_type == "sched_switch"
			and f"next_pid={pid}" in event.details),
		None
		)

		startup_latency = re.search(r'Latency:\s+(\d+\.\d+)\s+usecs', first_scheduled_details)
		startup_latency = float(startup_latency.group(1))


		#Debug print all times
		print(
			f"{Fore.CYAN}{Style.BRIGHT}PID: {pid} Start: {start_time}s Latency: {startup_latency} usec Exit: {exit_time}s{Style.RESET_ALL}")

		#Check that all time are not none and that start<exit and latency <start-exit
		if None in (start_time, startup_latency, exit_time):
			print(
				f"{Fore.RED}{Style.BRIGHT}Error: Missing times for PID {pid}{Style.RESET_ALL}")
			exit(-1)
		if start_time > exit_time or (startup_latency / 1_000_000) > (exit_time - start_time):
			print(
				f"{Fore.RED}{Style.BRIGHT}Error: Invalid times for PID {pid}: {start_time} {startup_latency} {exit_time}{Style.RESET_ALL}")
			exit(-1)

		workload_times[pid] = {
			"start_time": start_time,
			"startup_latency": startup_latency,
			"exit_time": exit_time
		}


if __name__ == "__main__":
	main()
