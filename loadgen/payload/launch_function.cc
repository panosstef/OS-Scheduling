#include <iostream>
#include <unistd.h>
#include <cstdlib>

unsigned long long fibonacci(int n) {
    if (n <= 1) {
        return 1;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}

int main(int argc, char *argv[]) {

    // Add the process to a cgroup for workload management
    std::string pid = std::to_string(getpid());
    std::string command = "echo " + pid + " > /sys/fs/cgroup/loadgen/workload/cgroup.procs";
    int ret = std::system(command.c_str());
    if (ret != 0) {
        std::cout << "Failed to add to workload cgroup" << std::endl;
        return -1;
    }

    int arg = atoi(argv[1]);
    unsigned long long n = fibonacci(arg);
    std::cout << "pid: " << pid << " fib(" << arg << "): " << n << std::endl;
    return 0;
}