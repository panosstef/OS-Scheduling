SCHED_NAME ?= scx_serverless
BPF_FILE   = $(SCHED_NAME).bpf.c
USER_FILE  = $(SCHED_NAME).c
BPF_OBJ    = $(SCHED_NAME).bpf.o
BPF_OBJ_DEBUG = $(SCHED_NAME)_debug.bpf.o
SKEL_H     = $(SCHED_NAME).bpf.skel.h
SKEL_H_DEBUG = $(SCHED_NAME)_debug.bpf.skel.h
BINARY     = $(SCHED_NAME)
BINARY_DEBUG = $(SCHED_NAME)_debug

ASK_DIR           = ask_userspace
ASK_SCHED_NAME    = scx_serverless_ask_userspace
ASK_BPF_FILE      = $(ASK_DIR)/$(ASK_SCHED_NAME).bpf.c
ASK_USER_FILE     = $(ASK_DIR)/$(ASK_SCHED_NAME).c
ASK_BPF_OBJ       = $(ASK_DIR)/$(ASK_SCHED_NAME).bpf.o
ASK_BPF_OBJ_DEBUG = $(ASK_DIR)/$(ASK_SCHED_NAME)_debug.bpf.o
ASK_SKEL_H        = $(ASK_DIR)/$(ASK_SCHED_NAME).bpf.skel.h
ASK_SKEL_H_DEBUG  = $(ASK_DIR)/$(ASK_SCHED_NAME)_debug.bpf.skel.h
ASK_BINARY        = $(ASK_DIR)/$(ASK_SCHED_NAME)
ASK_BINARY_DEBUG  = $(ASK_DIR)/$(ASK_SCHED_NAME)_debug

CC       = gcc
CLANG    = clang
BPFTOOL  = bpftool

CFLAGS     = -O2 -Wall -g
BPF_CFLAGS = -O2 -Wall -g -target bpf

LIBBPF_DIR   = /usr/lib/x86_64-linux-gnu

LDFLAGS = -L$(LIBBPF_DIR) -lbpf -lelf -lz

.PHONY: all clean install debug release run run-debug \
	ask-release ask-debug ask-run ask-run-debug

# Build both versions by default
all: release debug

# Build and run the release version
run: $(BINARY)
	sudo ./$(BINARY)

# Build and run the debug version
run-debug: $(BINARY_DEBUG)
	sudo ./$(BINARY_DEBUG)

# Build and run the ask_userspace release version
ask-run: $(ASK_BINARY)
	sudo ./$(ASK_BINARY)

# Build and run the ask_userspace debug version
ask-run-debug: $(ASK_BINARY_DEBUG)
	sudo ./$(ASK_BINARY_DEBUG)

# Release version (no debug messages)
release: $(BINARY)

# Debug version (with debug messages)
debug: $(BINARY_DEBUG)

# Release version (ask_userspace)
ask-release: $(ASK_BINARY)

# Debug version (ask_userspace)
ask-debug: $(ASK_BINARY_DEBUG)

# Generate BTF-based vmlinux.h (type definitions for BPF)
include/vmlinux.h:
	@mkdir -p include
	$(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > $@

# Build BPF object (release version - no debug)
$(BPF_OBJ): $(BPF_FILE) include/vmlinux.h
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@ \
		-I. \
		-Iinclude \

# Build BPF object (ask_userspace release)
$(ASK_BPF_OBJ): $(ASK_BPF_FILE) include/vmlinux.h
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@ \
		-I. \
		-Iinclude \
		-I$(ASK_DIR) \

# Build BPF object (debug version - with DEBUG defined)
$(BPF_OBJ_DEBUG): $(BPF_FILE) include/vmlinux.h
	$(CLANG) $(BPF_CFLAGS) -DDEBUG -c $< -o $@ \
		-I. \
		-Iinclude \

# Build BPF object (ask_userspace debug)
$(ASK_BPF_OBJ_DEBUG): $(ASK_BPF_FILE) include/vmlinux.h
	$(CLANG) $(BPF_CFLAGS) -DDEBUG -c $< -o $@ \
		-I. \
		-Iinclude \
		-I$(ASK_DIR) \

# Generate skeleton header (release)
$(SKEL_H): $(BPF_OBJ)
	$(BPFTOOL) gen skeleton $< name $(SCHED_NAME) > $@

# Generate skeleton header (ask_userspace release)
$(ASK_SKEL_H): $(ASK_BPF_OBJ)
	$(BPFTOOL) gen skeleton $< name $(ASK_SCHED_NAME) > $@

# Generate skeleton header (debug)
$(SKEL_H_DEBUG): $(BPF_OBJ_DEBUG)
	$(BPFTOOL) gen skeleton $< name $(SCHED_NAME)_debug > $@

# Generate skeleton header (ask_userspace debug)
$(ASK_SKEL_H_DEBUG): $(ASK_BPF_OBJ_DEBUG)
	$(BPFTOOL) gen skeleton $< name $(ASK_SCHED_NAME)_debug > $@

# Build user-space loader (release)
$(BINARY): $(USER_FILE) $(SKEL_H)
	$(CC) $(CFLAGS) -I. -Iinclude $< -o $@ $(LDFLAGS)

# Build user-space loader (ask_userspace release)
$(ASK_BINARY): $(ASK_USER_FILE) $(ASK_SKEL_H)
	$(CC) $(CFLAGS) -I. -Iinclude -I$(ASK_DIR) $< -o $@ $(LDFLAGS)

# Build user-space loader (debug)
$(BINARY_DEBUG): $(USER_FILE) $(SKEL_H_DEBUG)
	$(CC) $(CFLAGS) -DDEBUG_BUILD -I. -Iinclude $< -o $@ $(LDFLAGS)

# Build user-space loader (ask_userspace debug)
$(ASK_BINARY_DEBUG): $(ASK_USER_FILE) $(ASK_SKEL_H_DEBUG)
	$(CC) $(CFLAGS) -DDEBUG_BUILD -I. -Iinclude -I$(ASK_DIR) $< -o $@ $(LDFLAGS)

clean:
	rm -f $(BPF_OBJ) $(BPF_OBJ_DEBUG) $(SKEL_H) $(SKEL_H_DEBUG) $(BINARY) $(BINARY_DEBUG)
	rm -f $(ASK_BPF_OBJ) $(ASK_BPF_OBJ_DEBUG) $(ASK_SKEL_H) $(ASK_SKEL_H_DEBUG) $(ASK_BINARY) $(ASK_BINARY_DEBUG)
	rm -rf include/

install: $(BINARY) $(BINARY_DEBUG)
	sudo cp $(BINARY) /usr/local/bin/
	sudo cp $(BINARY_DEBUG) /usr/local/bin/
