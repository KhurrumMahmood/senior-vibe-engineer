CC = clang
CPPFLAGS = -I$(CURDIR)/include -I$(CURDIR)/src -DPILOT_FEATURE=1
CFLAGS = -std=c17 -Wall -Wextra -Werror -pedantic -fno-common
BUILD_DIR = .native-build
SOURCES = src/invoice.c src/main.c
OBJECTS = $(BUILD_DIR)/invoice.o $(BUILD_DIR)/main.o

.PHONY: all clean compile-db test

all: $(BUILD_DIR)/c-pilot-smoke

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/invoice.o: src/invoice.c include/cpilot/invoice.h src/invoice_internal.h src/pilot_mode.inc | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/invoice.c -o $@

$(BUILD_DIR)/main.o: src/main.c include/cpilot/invoice.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/main.c -o $@

$(BUILD_DIR)/c-pilot-smoke: $(OBJECTS)
	$(CC) $(CFLAGS) $(OBJECTS) -o $@

test: $(BUILD_DIR)/c-pilot-smoke
	@test "$$($(BUILD_DIR)/c-pilot-smoke)" = "invoice:INV-42:1:pilot"

compile-db: | $(BUILD_DIR)
	@printf '[\n  {"directory":"%s","file":"%s/src/invoice.c","arguments":["%s","-std=c17","-Wall","-Wextra","-Werror","-pedantic","-fno-common","-I%s/include","-I%s/src","-DPILOT_FEATURE=1","-c","%s/src/invoice.c","-o","%s/.native-build/invoice.o"]},\n  {"directory":"%s","file":"%s/src/main.c","arguments":["%s","-std=c17","-Wall","-Wextra","-Werror","-pedantic","-fno-common","-I%s/include","-I%s/src","-DPILOT_FEATURE=1","-c","%s/src/main.c","-o","%s/.native-build/main.o"]}\n]\n' "$(CURDIR)" "$(CURDIR)" "$(CC)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CC)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" > compile_commands.json

clean:
	rm -rf $(BUILD_DIR) compile_commands.json
