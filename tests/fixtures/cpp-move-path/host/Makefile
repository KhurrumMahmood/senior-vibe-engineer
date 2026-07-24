CXX = clang++
CPPFLAGS = -I$(CURDIR)/include -I$(CURDIR)/src
CXXFLAGS = -std=c++20 -Wall -Wextra -Werror -pedantic
BUILD_DIR = .native-build
SOURCES = src/invoice.cpp src/main.cpp tests/invoice_test.cpp
OBJECTS = $(BUILD_DIR)/invoice.o $(BUILD_DIR)/main.o $(BUILD_DIR)/invoice_test.o

.PHONY: all clean compile-db test

all: $(BUILD_DIR)/cpp-move-smoke

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/invoice.o: src/invoice.cpp include/cppmove/invoice.hpp src/invoice_internal.hpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/invoice.cpp -o $@

$(BUILD_DIR)/main.o: src/main.cpp include/cppmove/invoice.hpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/main.cpp -o $@

$(BUILD_DIR)/invoice_test.o: tests/invoice_test.cpp include/cppmove/invoice.hpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/tests/invoice_test.cpp -o $@

$(BUILD_DIR)/cpp-move-smoke: $(BUILD_DIR)/invoice.o $(BUILD_DIR)/main.o
	$(CXX) $(CXXFLAGS) $^ -o $@

$(BUILD_DIR)/cpp-move-test: $(BUILD_DIR)/invoice.o $(BUILD_DIR)/invoice_test.o
	$(CXX) $(CXXFLAGS) $^ -o $@

test: $(BUILD_DIR)/cpp-move-test $(BUILD_DIR)/cpp-move-smoke
	@$(BUILD_DIR)/cpp-move-test

compile-db: | $(BUILD_DIR)
	@printf '[\n  {"directory":"%s","file":"%s/src/invoice.cpp","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-c","%s/src/invoice.cpp","-o","%s/.native-build/invoice.o"]},\n  {"directory":"%s","file":"%s/src/main.cpp","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-c","%s/src/main.cpp","-o","%s/.native-build/main.o"]},\n  {"directory":"%s","file":"%s/tests/invoice_test.cpp","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-c","%s/tests/invoice_test.cpp","-o","%s/.native-build/invoice_test.o"]}\n]\n' "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" > compile_commands.json

clean:
	rm -rf $(BUILD_DIR) compile_commands.json
