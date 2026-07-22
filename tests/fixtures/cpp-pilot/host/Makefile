CXX = clang++
CPPFLAGS = -I$(CURDIR)/include -I$(CURDIR)/src -DPILOT_FEATURE=1
CXXFLAGS = -std=c++20 -Wall -Wextra -Werror -pedantic
BUILD_DIR = .native-build
SOURCES = src/invoice.cpp src/main.cpp
OBJECTS = $(BUILD_DIR)/invoice.o $(BUILD_DIR)/main.o

.PHONY: all clean compile-db test

all: $(BUILD_DIR)/cpp-pilot-smoke

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/invoice.o: src/invoice.cpp include/cpppilot/invoice.hpp include/cpppilot/render.hpp src/invoice_internal.hpp src/pilot_mode.inc | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/invoice.cpp -o $@

$(BUILD_DIR)/main.o: src/main.cpp include/cpppilot/invoice.hpp include/cpppilot/render.hpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/main.cpp -o $@

$(BUILD_DIR)/cpp-pilot-smoke: $(OBJECTS)
	$(CXX) $(CXXFLAGS) $(OBJECTS) -o $@

test: $(BUILD_DIR)/cpp-pilot-smoke
	@test "$$($(BUILD_DIR)/cpp-pilot-smoke)" = "invoice:INV-42:pending:pilot"

compile-db: | $(BUILD_DIR)
	@printf '[\n  {"directory":"%s","file":"%s/src/invoice.cpp","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-DPILOT_FEATURE=1","-c","%s/src/invoice.cpp","-o","%s/.native-build/invoice.o"]},\n  {"directory":"%s","file":"%s/src/main.cpp","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-DPILOT_FEATURE=1","-c","%s/src/main.cpp","-o","%s/.native-build/main.o"]}\n]\n' "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" > compile_commands.json

clean:
	rm -rf $(BUILD_DIR) compile_commands.json
