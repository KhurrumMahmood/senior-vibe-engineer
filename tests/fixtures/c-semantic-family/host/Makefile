CC = clang
CPPFLAGS = -I$(CURDIR)/include
CFLAGS = -std=c17 -Wall -Wextra -Werror -pedantic -fno-common
BUILD_DIR = .native-build
SOURCES = src/semantic.c src/clean.c src/main.c
OBJECTS = $(BUILD_DIR)/semantic.o $(BUILD_DIR)/clean.o $(BUILD_DIR)/main.o

.PHONY: all clean compile-db test

all: $(BUILD_DIR)/c-semantic-smoke

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/semantic.o: src/semantic.c include/csemantic/semantic.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/semantic.c -o $@

$(BUILD_DIR)/clean.o: src/clean.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/clean.c -o $@

$(BUILD_DIR)/main.o: src/main.c include/csemantic/semantic.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/main.c -o $@

$(BUILD_DIR)/c-semantic-smoke: $(OBJECTS)
	$(CC) $(CFLAGS) $(OBJECTS) -o $@

test: $(BUILD_DIR)/c-semantic-smoke
	@test "$$($(BUILD_DIR)/c-semantic-smoke)" = "semantic:running:us:112:1:legacy_status"

compile-db: | $(BUILD_DIR)
	@printf '[\n  {"directory":"%s","file":"%s/src/semantic.c","arguments":["%s","-std=c17","-Wall","-Wextra","-Werror","-pedantic","-fno-common","-I%s/include","-c","%s/src/semantic.c","-o","%s/.native-build/semantic.o"]},\n  {"directory":"%s","file":"%s/src/clean.c","arguments":["%s","-std=c17","-Wall","-Wextra","-Werror","-pedantic","-fno-common","-I%s/include","-c","%s/src/clean.c","-o","%s/.native-build/clean.o"]},\n  {"directory":"%s","file":"%s/src/main.c","arguments":["%s","-std=c17","-Wall","-Wextra","-Werror","-pedantic","-fno-common","-I%s/include","-c","%s/src/main.c","-o","%s/.native-build/main.o"]}\n]\n' "$(CURDIR)" "$(CURDIR)" "$(CC)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CC)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CC)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" > compile_commands.json

clean:
	rm -rf $(BUILD_DIR) compile_commands.json
