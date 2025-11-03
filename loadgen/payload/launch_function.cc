#include <iostream>
#include <unistd.h>
#include <cstdlib>
#include <fstream>

unsigned long long fibonacci(int n) {
    if (n <= 1) {
        return 1;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}

int main(int argc, char *argv[]) {
    std::string pid = std::to_string(getpid());

    int arg = atoi(argv[1]);
    unsigned long long n = fibonacci(arg);
        std::cout << pid << ' ' << n << '\n';
    return 0;
}