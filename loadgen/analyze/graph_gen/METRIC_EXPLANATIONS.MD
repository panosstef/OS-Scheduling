### Metrics Description

#### Per process times (per_proc_times.png)

*Timings for each process of the workload, this is on a per workload item (process) basis*

- **Response Time (ms)**:
Time passed from the fork on the process to the first schedule in

- **Execution Time (s)**:
Time spent from the first schedule in to the process exit (sched_exit). This counts all the time that could be spent not running (waiting) after the first schedule in

- **Turnaround Time (s)**:
Total workload time (from the fork to the process exit), *thus response + execution time*

- **Load Balancing Migrations**:
  CDF showing the number of migrations from one CPU to another per workload item. This doesn't count the starting migrate event to set the task's affinity.

#### Per process statistics (per_proc_statistics.png)

*All these values are metrics on a per task basis (meaning one value for each one of the workload tasks the simulation executes)*

- **Total Runtime (ms)**:
  Time spent running on a CPU *(Cpu burst between sched-in and sched-out)*

- **Contenct Switches**:
  Number of scheduler switches after execution (after sched_exec for each workload task)

- **Scheduling Delays [avg] (ms)**:
  Time a task was ready to run but was kept waiting (average and maximum values)

- **Burst Run Times**:
  Avg CPU Burst time between sched-in and out of a task

- **Schedule-in count !(Commented out in code, similar to Context Switches)!**:
  Number of times each PID was scheduled in (sched_fork to sched_exit). Similar to Context Switches but it counts also the sched_switches that happened before the sched_exec for the workload function

#### Scheduling latencies statistics (sched_latencies_statistics.png)

*Statistics taken from every scheduling switch that happened over the workload execution.<br>
These might resemble the per task statistics but each value (and thus the CDF) is per sched switch event*

- **Wait time**:
	Time between the previous sched-out for each sched-in event

- **Scheduling Delay**:
	Time between runnable and actually running (wakeup and sched in)

- **Run Time**:
	Run time burst after each sched in till the next sched out

#### Scheduling delays over time (timeseries_scheduling_delays.png)

*Scatter diagram showing scheduling delay (when a task was ready to run but was kept waiting - from sched_wakeup to sched_switch)*

#### General statistics (general_stats.png)

- **Total Runtime (s)**:
Total runtime for the whole workload

- **Total context Switches**:
Total context switches that happened during the workload execution

- **Total Cpu Idle Time**:
Total time that a cpu was idle

- **Individual CPU Idle Times**:
Total idle time per cpu for each setup

#### Cpu utilization over time (timeseries_cpu_utilization.png)

*Average system cpu utlization over time per dataset. Graphed together with min/max utilization range*

#### Cpu (per core) utilization over time as heatmap (heatmap_cpu_utilization.png)

*Per core cpu utilization over time per dataset graphed as a heatmap*