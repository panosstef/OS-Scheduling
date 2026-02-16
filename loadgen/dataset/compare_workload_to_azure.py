#!/usr/bin/env python3
import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt

dur_df_list = []
days = [
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
    "12",
    "13",
    "14",
]

__file = os.path.dirname(os.path.realpath(__file__))
for i in days:
    dur_filename = f"{__file}/trace/function_durations_percentiles.anon.d{i}.csv"

    dur_df = pd.read_csv(dur_filename)
    dur_df_list.append(dur_df)

duration_df = pd.concat(dur_df_list, axis=0, ignore_index=True).iloc[:, [3, 4]]

duration_df = duration_df[duration_df["Average"] > 0]

duration_df = duration_df.groupby("Average").sum().reset_index()

# prepare the two-week CDF (used in the combined plot)
x_2weeks = list(duration_df["Average"] / 1000)
y_2weeks = list(duration_df["Count"])
p_2weeks = y_2weeks / np.sum(y_2weeks)
cdf_2weeks = np.cumsum(p_2weeks)


# These match the bucket definitions in gen_workload.py
dur_list = [7, 8, 9, 10, 12, 14, 17, 21, 27, 39, 56, 85, 131, 205, 325, 520, 838, 1347, 2175, 3512, 5673, 9172, 14835]
fib = [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46]
arg_to_duration = dict(zip(fib, dur_list))

# Load generated workload and build its CDF
workload_file = f"{__file}/workload_dur.txt"
if not os.path.exists(workload_file):
    raise FileNotFoundError(f"No workload file found at: {workload_file}")
fig, ax1 = plt.subplots(figsize=(12, 6))
ax1.step(
    x_2weeks,
    cdf_2weeks,
    color="lightcoral",
    where="pre",
    linewidth=3,
    label="Azure two weeks data",
)
workload_df = pd.read_csv(workload_file, sep=r"\s+", header=None, names=["iat", "arg"])
workload_counts = workload_df["arg"].value_counts().sort_index()

workload_duration_counts = []
for arg, count in workload_counts.items():
    if arg in arg_to_duration:
        workload_duration_counts.append((arg_to_duration[arg], count))

workload_duration_counts.sort(key=lambda x: x[0])
x = [duration for duration, _ in workload_duration_counts]
y = [count for _, count in workload_duration_counts]
p = y / np.sum(y)
cdf = np.cumsum(p)
x_divided = [value / 1000 for value in x]

ax1.step(
    x_divided,
    cdf,
    color="cornflowerblue",
    where="pre",
    linewidth=3,
    label="Sampled data",
)
plt.xticks(size=20)
plt.yticks(size=20)
plt.grid()
plt.xscale("log")
ax1.set_xlabel("Average Duration (s)", size=23)
ax1.set_ylabel("Cumulative prob", size=23)
plt.legend(fontsize=20)
plt.tight_layout()
plt.savefig("azure_sample_comparison.png", dpi=300)
