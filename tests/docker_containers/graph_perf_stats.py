import re
import matplotlib.pyplot as plt
import numpy as np

def strip_ansi(text):
	return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)

# Function to parse the perf output file
def parse_perf_output(file_path):
	with open(file_path, 'r') as f:
		data = strip_ansi(f.read())

	cpu_migrations = int(re.search(r'(\d+)\s+cpu-migrations', data).group(1))
	sched_switch = int(re.search(r'(\d+)\s+sched:sched_switch', data).group(1))
	sched_wakeup = int(re.search(r'(\d+)\s+sched:sched_wakeup', data).group(1))
	avg_execution_time = float(re.search(r'Average container execution time*:\s*(\d+\.\d+)', data).group(1))
	total_execution_time = float(re.search(r'Total execution time*:\s*(\d+\.\d+)', data).group(1))
	p99 = float(re.search(r'99th percentile container execution time*:\s*(\d+\.\d+)', data).group(1))
 
	return {
		'cpu_migrations': cpu_migrations,
		'context_switches': sched_switch,
		'sched_wakeup': sched_wakeup,
		'avg_execution_time': avg_execution_time,
		'total_execution_time': total_execution_time,
		'p99': p99
	}

# Function to plot the data
def plot_scheduler_comparison(data_6_5_9, data_6_12):
	fig, ax = plt.subplots(figsize=(7, 6))

	labels = ['context_switches', 'sched_wakeup']
	data_6_5_9_sched = [data_6_5_9[label] for label in labels]
	data_6_12_sched = [data_6_12[label] for label in labels]

	ax.bar(labels, data_6_5_9_sched, width=-0.4, label="6.5.9", align='edge')
	ax.bar(labels, data_6_12_sched, width=0.4, label="6.12", align='edge')

	# Show values on top of the bars
	for i, value in enumerate(data_6_5_9_sched):
		ax.text(i - 0.2, value + 1000, str(value), ha='center', va='bottom', fontsize=14)
	for i, value in enumerate(data_6_12_sched):
		ax.text(i + 0.2, value + 1000, str(value), ha='center', va='bottom', fontsize=14)

	ax.set_title('Scheduler Events Comparison')
	ax.set_ylabel('Event Count')
	ax.legend()
	plt.tight_layout()
	plt.show()

def plot_other_counters_comparison(data_6_5_9, data_6_12):
	fig, ax = plt.subplots(figsize=(7, 6))

	labels_other = ['context_switches', 'cpu_migrations']
	data_6_5_9_other = [data_6_5_9[label] for label in labels_other]
	data_6_12_other = [data_6_12[label] for label in labels_other]

	ax.bar(labels_other, data_6_5_9_other, width=-0.4, label="6.5.9", align='edge')
	ax.bar(labels_other, data_6_12_other, width=0.4, label="6.12", align='edge')

	# Show values on top of the bars
	for i, value in enumerate(data_6_5_9_other):
		ax.text(i - 0.2, value + 500, str(value), ha='center', va='bottom', fontsize=14)
	for i, value in enumerate(data_6_12_other):
		ax.text(i + 0.2, value + 500, str(value), ha='center', va='bottom', fontsize=14)

	ax.set_title('Other Performance Counters Comparison')
	ax.set_ylabel('Event Count')
	ax.legend()

	plt.tight_layout()
	plt.show()
def plot_execution_time_comparison(data_6_5_9, data_6_12):
	fig, ax = plt.subplots(figsize=(7, 6))

	avg_times = [data_6_5_9['avg_execution_time'], data_6_12['avg_execution_time']]
	total_times = [data_6_5_9['total_execution_time'], data_6_12['total_execution_time']]
	p99_times = [data_6_5_9['p99'], data_6_12['p99']]

	labels = ['6.5.9', '6.12']
	x = np.arange(len(labels))

	width = 0.25

	total_bars = ax.bar(x - width, total_times, width=width, color='blue', alpha=0.5,
						hatch='/', label='Total Execution Time')
	avg_bars = ax.bar(x, avg_times, width=width, color='orange', label='Average Execution Time')
	p99_bars = ax.bar(x + width, p99_times, width=width, color='green', alpha=0.7,
					  label='99th Percentile Execution Time')

	for i, value in enumerate(avg_times):
		ax.text(i, value + 0.03, f'Avg: {value:.3f}s', ha='center', va='bottom', fontsize=10, fontweight='bold')
	for i, value in enumerate(total_times):
		ax.text(i - width, value + 0.01, f'Total: {value:.3f}s', ha='center', va='bottom', fontsize=10, fontweight='bold')
	for i, value in enumerate(p99_times):
		ax.text(i + width, value + 0.01, f'P99: {value:.3f}s', ha='center', va='bottom', fontsize=10, fontweight='bold')

	ax.set_title('Execution Time Comparison: 6.5.9 vs 6.12', fontsize=14)
	ax.set_ylabel('Execution Time (seconds)', fontsize=12)
	ax.set_xticks(x)
	ax.set_xticklabels(labels)

	ax.legend(fontsize=10)
	ax.grid(axis='y', linestyle='--', alpha=0.7)
	plt.tight_layout()

	plt.show()


# Parse both output files
data_6_5_9 = parse_perf_output('perf_6.5.9.out')
data_6_12 = parse_perf_output('perf_6.12.out')

# Generate separate plots
# plot_scheduler_comparison(data_6_5_9, data_6_12)
# plot_other_counters_comparison(data_6_5_9, data_6_12)
plot_execution_time_comparison(data_6_5_9, data_6_12)
