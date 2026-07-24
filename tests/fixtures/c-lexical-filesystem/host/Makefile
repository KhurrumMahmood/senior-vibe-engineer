CC = clang
CPPFLAGS = -I$(CURDIR)/include -I$(CURDIR)/src
CFLAGS = -std=c17 -Wall -Wextra -Werror -pedantic -fno-common
BUILD_DIR = .native-build
LIB_OBJECTS = $(BUILD_DIR)/billing_parser.o $(BUILD_DIR)/billing_validator.o $(BUILD_DIR)/billing_types.o

.PHONY: all clean compile-db test

all: $(BUILD_DIR)/c-lexical-smoke

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/billing_parser.o: src/billing_parser.c include/cbilling/invoice.h src/billing_internal.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/billing_parser.c -o $@

$(BUILD_DIR)/billing_validator.o: src/billing_validator.c include/cbilling/invoice.h src/billing_internal.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/billing_validator.c -o $@

$(BUILD_DIR)/billing_types.o: src/billing_types.c include/cbilling/invoice.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/billing_types.c -o $@

$(BUILD_DIR)/main.o: src/main.c include/cbilling/invoice.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/main.c -o $@

$(BUILD_DIR)/c-lexical-smoke: $(LIB_OBJECTS) $(BUILD_DIR)/main.o
	$(CC) $(CFLAGS) $^ -o $@

$(BUILD_DIR)/native_test.o: tests/native_test.c include/cbilling/invoice.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $(CURDIR)/tests/native_test.c -o $@

$(BUILD_DIR)/native-test: $(LIB_OBJECTS) $(BUILD_DIR)/native_test.o
	$(CC) $(CFLAGS) $^ -o $@

test: $(BUILD_DIR)/native-test $(BUILD_DIR)/c-lexical-smoke
	@$(BUILD_DIR)/native-test
	@test "$$($(BUILD_DIR)/c-lexical-smoke)" = "c-lexical-smoke:132"

compile-db: | $(BUILD_DIR)
	@printf '[\n  {"directory":"%s","file":"%s/src/billing_parser.c","arguments":["%s","-std=c17","-Wall","-Wextra","-Werror","-pedantic","-fno-common","-I%s/include","-I%s/src","-c","%s/src/billing_parser.c","-o","%s/.native-build/billing_parser.o"]},\n  {"directory":"%s","file":"%s/src/billing_types.c","arguments":["%s","-std=c17","-Wall","-Wextra","-Werror","-pedantic","-fno-common","-I%s/include","-I%s/src","-c","%s/src/billing_types.c","-o","%s/.native-build/billing_types.o"]},\n  {"directory":"%s","file":"%s/src/billing_validator.c","arguments":["%s","-std=c17","-Wall","-Wextra","-Werror","-pedantic","-fno-common","-I%s/include","-I%s/src","-c","%s/src/billing_validator.c","-o","%s/.native-build/billing_validator.o"]},\n  {"directory":"%s","file":"%s/src/clean/unique.c","arguments":["%s","-std=c17","-Wall","-Wextra","-Werror","-pedantic","-fno-common","-I%s/include","-I%s/src","-c","%s/src/clean/unique.c","-o","%s/.native-build/unique.o"]},\n  {"directory":"%s","file":"%s/src/main.c","arguments":["%s","-std=c17","-Wall","-Wextra","-Werror","-pedantic","-fno-common","-I%s/include","-I%s/src","-c","%s/src/main.c","-o","%s/.native-build/main.o"]}\n]\n' "$(CURDIR)" "$(CURDIR)" "$(CC)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CC)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CC)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CC)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CC)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" > compile_commands.json

clean:
	rm -rf $(BUILD_DIR) compile_commands.json
