SCHED_NAME ?= scx_serverless
BPF_FILE   = $(SCHED_NAME).bpf.c
USER_FILE  = $(SCHED_NAME).c
BPF_OBJ    = $(SCHED_NAME).bpf.o
BPF_OBJ_DEBUG = $(SCHED_NAME)_debug.bpf.o
SKEL_H     = $(SCHED_NAME).bpf.skel.h
SKEL_H_DEBUG = $(SCHED_NAME)_debug.bpf.skel.h
BINARY     = $(SCHED_NAME)
BINARY_DEBUG = $(SCHED_NAME)_debug

CC       = gcc
CLANG    = clang
BPFTOOL  = bpftool

CFLAGS     = -O2 -Wall -g
BPF_CFLAGS = -O2 -Wall -g -target bpf

LIBBPF_DIR   = /usr/lib/x86_64-linux-gnu

LDFLAGS = -L$(LIBBPF_DIR) -lbpf -lelf -lz

.PHONY: all clean install debug release

# Build both versions by default
all: release debug

# Release version (no debug messages)
release: $(BINARY)

# Debug version (with debug messages)
debug: $(BINARY_DEBUG)

# Generate BTF-based vmlinux.h (type definitions for BPF)
include/vmlinux.h:
	@mkdir -p include
	$(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > $@

# Build BPF object (release version - no debug)
$(BPF_OBJ): $(BPF_FILE) include/vmlinux.h
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@ \
		-I. \
		-Iinclude \

# Build BPF object (debug version - with DEBUG defined)
$(BPF_OBJ_DEBUG): $(BPF_FILE) include/vmlinux.h
	$(CLANG) $(BPF_CFLAGS) -DDEBUG -c $< -o $@ \
		-I. \
		-Iinclude \

# Generate skeleton header (release)
$(SKEL_H): $(BPF_OBJ)
	$(BPFTOOL) gen skeleton $< name $(SCHED_NAME) > $@

# Generate skeleton header (debug)
$(SKEL_H_DEBUG): $(BPF_OBJ_DEBUG)
	$(BPFTOOL) gen skeleton $< name $(SCHED_NAME)_debug > $@

# Build user-space loader (release)
$(BINARY): $(USER_FILE) $(SKEL_H)
	$(CC) $(CFLAGS) -I. -Iinclude $< -o $@ $(LDFLAGS)

# Build user-space loader (debug)
$(BINARY_DEBUG): $(USER_FILE) $(SKEL_H_DEBUG)
	$(CC) $(CFLAGS) -DDEBUG_BUILD -I. -Iinclude $< -o $@ $(LDFLAGS)

clean:
	rm -f $(BPF_OBJ) $(BPF_OBJ_DEBUG) $(SKEL_H) $(SKEL_H_DEBUG) $(BINARY) $(BINARY_DEBUG)
	rm -rf include/

install: $(BINARY) $(BINARY_DEBUG)
	sudo cp $(BINARY) /usr/local/bin/
	sudo cp $(BINARY_DEBUG) /usr/local/bin/
