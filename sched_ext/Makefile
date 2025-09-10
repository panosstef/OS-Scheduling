SCHED_NAME ?= scx_serverless
BPF_FILE   = $(SCHED_NAME).bpf.c
USER_FILE  = $(SCHED_NAME).c
BPF_OBJ    = $(BPF_FILE).o
SKEL_H     = $(SCHED_NAME).bpf.skel.h

CC       = gcc
CLANG    = clang
BPFTOOL  = bpftool

CFLAGS     = -O2 -Wall -g
BPF_CFLAGS = -O2 -Wall -g -target bpf

LIBBPF_DIR   = /usr/lib/x86_64-linux-gnu

LDFLAGS = -L$(LIBBPF_DIR) -lbpf -lelf -lz

.PHONY: all clean install

all: $(SCHED_NAME)

# Generate BTF-based vmlinux.h (type definitions for BPF)
include/vmlinux.h:
	@mkdir -p include
	$(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > $@

# Build BPF object
$(BPF_OBJ): $(BPF_FILE) include/vmlinux.h
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@ \
		-I. \
		-Iinclude \

# Generate skeleton header
$(SKEL_H): $(BPF_OBJ)
	$(BPFTOOL) gen skeleton $< name $(SCHED_NAME) > $@

# Build user-space loader
$(SCHED_NAME): $(USER_FILE) $(SKEL_H)
	$(CC) $(CFLAGS) -I. -Iinclude $< -o $@ $(LDFLAGS)

clean:
	rm -f $(BPF_OBJ) $(SKEL_H) $(SCHED_NAME)
	rm -rf include/

install: $(SCHED_NAME)
	sudo cp $(SCHED_NAME) /usr/local/bin/
