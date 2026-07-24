CC = clang
CPPFLAGS = -I$(CURDIR)/include
CFLAGS = -std=c17 -Wall -Wextra -Werror -pedantic -fno-common
BUILD_DIR = .native-build
SOURCES = src/legacy.c src/billing_parser.c src/billing_types.c src/billing_validator.c src/main.c
OBJECTS = $(SOURCES:src/%.c=$(BUILD_DIR)/%.o)

.PHONY: all clean compile-db test

all: $(BUILD_DIR)/c-structure-smoke

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/%.o: src/%.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $(CURDIR)/$< -o $@

$(BUILD_DIR)/c-structure-smoke: $(OBJECTS)
	$(CC) $(CFLAGS) $(OBJECTS) -o $@

$(BUILD_DIR)/native_test.o: tests/native_test.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $(CURDIR)/$< -o $@

$(BUILD_DIR)/native-test: $(BUILD_DIR)/legacy.o $(BUILD_DIR)/billing_validator.o $(BUILD_DIR)/native_test.o
	$(CC) $(CFLAGS) $^ -o $@

test: $(BUILD_DIR)/native-test $(BUILD_DIR)/c-structure-smoke
	@$(BUILD_DIR)/native-test
	@test "$$($(BUILD_DIR)/c-structure-smoke)" = "c-structure:16"

compile-db: | $(BUILD_DIR)
	@first=1; printf '[\n' > compile_commands.json; \
	for source in $(SOURCES); do \
		object=$${source#src/}; object=$${object%.c}; \
		if [ $$first -eq 0 ]; then printf ',\n' >> compile_commands.json; fi; \
		first=0; \
		printf '  {"directory":"%s","file":"%s/%s","arguments":["%s","-std=c17","-Wall","-Wextra","-Werror","-pedantic","-fno-common","-I%s/include","-c","%s/%s","-o","%s/.native-build/%s.o"]}' "$(CURDIR)" "$(CURDIR)" "$$source" "$(CC)" "$(CURDIR)" "$(CURDIR)" "$$source" "$(CURDIR)" "$$object" >> compile_commands.json; \
	done; printf '\n]\n' >> compile_commands.json

clean:
	rm -rf $(BUILD_DIR) compile_commands.json
