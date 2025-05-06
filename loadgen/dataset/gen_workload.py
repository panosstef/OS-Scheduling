#!/usr/bin/env python3
#https://azurepublicdatasettraces.blob.core.windows.net/azurepublicdatasetv2/azurefunctions_dataset2019/azurefunctions-dataset2019.tar.xz
import pandas as pd
import numpy as np
from collections import defaultdict

durations_file = "./function_durations_percentiles.anon.d01.csv"
invoke_file = "./invocations_per_function_md.anon.d01.csv"
workload_file = "workload_dur.txt"

duration_df = pd.read_csv(durations_file, usecols=["HashFunction", "Average"])
invoke_df = pd.read_csv(invoke_file, usecols=["HashFunction","1", "2"])

# Merge the duration and invocation dataframes by the HashFunction column
df = pd.merge(duration_df, invoke_df, how="inner", on=["HashFunction"])

df = df[df["Average"] > 0]
df = df[df["Average"] < 180000]
df = df.sort_values(by="Average")

duration_dict = defaultdict(lambda: [0] * (df.shape[1] - 2))

for _, row in df.iterrows():
	duration = list(row)[1]
	occur_list = list(row[2:])
	duration_dict[duration] = list(map(lambda x: x[0] + x[1], zip(duration_dict[duration], occur_list)))


# convert the dictionary to dataframe
duration_occurance = pd.DataFrame.from_dict(duration_dict, orient="index")
duration_occurance.index.name = "Duration"
duration_occurance.reset_index(inplace=True)

bucket = {}
for i in range(24, 47):
    bucket[i] = [0] * 2

# According to calibration, function duration and the corresponding fib N's

# dur_list = [14, 17, 22, 29, 40, 57, 87, 134, 212, 336, 538, 863, 1392, 2246, 3625, 5857, 9471, 15317]
# fib = [29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46]
dur_list = [7, 8, 9, 10, 12, 14, 17, 21, 27, 39, 56, 85, 131, 205, 325, 520, 838, 839, 1347, 2175, 3512, 5673, 9172, 14835]
fib = [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 40, 41, 42, 43, 44, 45, 46]

for index, row in duration_occurance.iterrows():
    Duration = list(row)[0]
    occur_list = list(row)[1:]
    for i in range(len(dur_list)):
        if Duration <= dur_list[i] or i == len(dur_list) - 1 and Duration > dur_list[i]:
            # Bucket the function invocation based on the duration
            bucket[fib[i]] = list(
                map(lambda x: x[0] + x[1], zip(bucket[fib[i]], occur_list))
            )
            break

arg_df = pd.DataFrame.from_dict(bucket, orient="index")
arg_df.index.name = "arg"
occur_time = []

# Generate the workload item for each minute
for minute in arg_df.columns[0:2]:
    for arg in arg_df.index:
        invoke_times = arg_df.loc[arg, minute] / 600  # downscale
        interval = 60 / invoke_times
        for n in range(int(invoke_times)):
            time = int(minute) * 60 + n * interval
            occur_time.append((time, str(arg)))

# Sort the items by time
sort_list = sorted(occur_time, key=lambda x: x[0])
time_list, arg_list = zip(*sort_list)
# Get the time difference between each item, which is the inter-arrival time
diff_list = time_list[0] + np.diff(list(time_list))
output_list = list(zip(diff_list, arg_list))

# Write the workload to a file
f = open(workload_file, "w")
for t in output_list:
    line = " ".join(str(x) for x in t)
    f.write(line + "\n")
f.close()
