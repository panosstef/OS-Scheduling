import sys

# Check if the file name is passed as a command-line argument
if len(sys.argv) != 2:
    print("Usage: python script.py <filename>")
    sys.exit(1)

# Get the filename from the command-line argument
filename = sys.argv[1]

# Try to open and read the file
try:
    with open(filename, 'r') as f:
        lines = f.readlines()
except FileNotFoundError:
    print(f"Error: File '{filename}' not found.")
    sys.exit(1)

# Initialize counters for different thresholds
count_above_0_9 = 0
count_above_1 = 0
count_above_1_5 = 0
count_above_3 = 0
count_above_5 = 0
count_above_10 = 0

# Iterate through the lines and check the percentage values
for line in lines:
    # Split the line into the number and the percentage value
    _, percentage_str = line.split(':')
    percentage = float(percentage_str.strip().replace('%', ''))
    
    # Check the thresholds
    if percentage > 0.9:
        count_above_0_9 += 1
    if percentage > 1:
        count_above_1 += 1
    if percentage > 1.5:
        count_above_1_5 += 1
    if percentage > 3:
        count_above_3 += 1
    if percentage > 5 :
        count_above_5 += 1
    if percentage > 10 :
        count_above_10 += 1

# Output the results
print(f'Count of values above 0.9%: {count_above_0_9}')
print(f'Count of values above 1%: {count_above_1}')
print(f'Count of values above 1.5%: {count_above_1_5}')
print(f'Count of values above 3%: {count_above_3}')
print(f'Count of values above 5%: {count_above_10}')
