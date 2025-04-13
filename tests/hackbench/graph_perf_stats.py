import re
import pandas as pd
import matplotlib.pyplot as plt

# Function to parse the perf output file
def parse_perf_output(file_path):
    with open(file_path, 'r') as f:
        data = f.read()

    cpu_migrations = int(re.search(r'(\d+)\s+cpu-migrations', data).group(1))
    sched_switch = int(re.search(r'(\d+)\s+sched:sched_switch', data).group(1))
    sched_wakeup = int(re.search(r'(\d+)\s+sched:sched_wakeup', data).group(1))
    sched_wakeup_new = int(re.search(r'(\d+)\s+sched:sched_wakeup_new', data).group(1))

    # Average execution time (you can adjust this based on the actual output)
    avg_execution_time = float(re.search(r'Average execution time.*:\s*(\d+\.\d+)', data).group(1))

    return {

        'cpu_migrations': cpu_migrations,
        'context_switches': sched_switch,
        'sched_wakeup': sched_wakeup,
        'avg_execution_time': avg_execution_time
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
        ax.text(i - 0.2, value + 5000, str(value), ha='center', va='bottom', fontsize=14)
    for i, value in enumerate(data_6_12_sched):
        ax.text(i + 0.2, value + 5000, str(value), ha='center', va='bottom', fontsize=14)

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

    # Plot average execution time
    avg_times = [data_6_5_9['avg_execution_time'], data_6_12['avg_execution_time']]
    labels = ['6.5.9', '6.12']

    ax.bar(labels, avg_times, color=['blue', 'orange'])

    # Show values on top of the bars
    for i, value in enumerate(avg_times):
        ax.text(i, value + 0.01, f'{value:.3f} s', ha='center', va='bottom', fontsize=14)

    ax.set_title('Average Execution Time Comparison')
    ax.set_ylabel('Execution Time (seconds)')
    ax.legend([f"Avg Exec Time"])


    
    plt.tight_layout()
    plt.show()

# Parse both output files
data_6_5_9 = parse_perf_output('hackbench_1_6.5.9_perf.out')
data_6_12 = parse_perf_output('hackbench_1_6.12_perf.out')

# Generate separate plots
plot_scheduler_comparison(data_6_5_9, data_6_12)
plot_other_counters_comparison(data_6_5_9, data_6_12)
plot_execution_time_comparison(data_6_5_9, data_6_12)
