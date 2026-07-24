CXX = clang++
CPPFLAGS = -I$(CURDIR)/src
CXXFLAGS = -std=c++20 -Wall -Wextra -Werror -pedantic
BUILD_DIR = .native-build
SOURCES = src/legacy.cpp src/billing_parser.cpp src/billing_rules.cpp src/billing_summary.cpp src/main.cpp
TEST_SOURCES = src/native_check.cpp
COMPILE_SOURCES = $(SOURCES) $(TEST_SOURCES)
OBJECTS = $(SOURCES:src/%.cpp=$(BUILD_DIR)/%.o)

.PHONY: all clean compile-db test

all: $(BUILD_DIR)/cpp-structure-smoke

$(BUILD_DIR):
	mkdir -p $@

$(BUILD_DIR)/%.o: src/%.cpp | $(BUILD_DIR)
	mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/$< -o $@

$(BUILD_DIR)/cpp-structure-smoke: $(OBJECTS)
	$(CXX) $(CXXFLAGS) $^ -o $@

$(BUILD_DIR)/cpp-structure-native: $(BUILD_DIR)/legacy.o $(BUILD_DIR)/billing_rules.o $(BUILD_DIR)/native_check.o
	$(CXX) $(CXXFLAGS) $^ -o $@

test: $(BUILD_DIR)/cpp-structure-smoke $(BUILD_DIR)/cpp-structure-native
	@$(BUILD_DIR)/cpp-structure-native
	@test "$$($(BUILD_DIR)/cpp-structure-smoke)" = "cpp-structure:18"

compile-db: | $(BUILD_DIR)
	@first=1; printf '[\n' > compile_commands.json; \
	for source in $(COMPILE_SOURCES); do \
		object=$${source#src/}; object=$${object%.cpp}; \
		if [ $$first -eq 0 ]; then printf ',\n' >> compile_commands.json; fi; \
		first=0; \
		printf '  {"directory":"%s","file":"%s/%s","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/src","-c","%s/%s","-o","%s/.native-build/%s.o"]}' "$(CURDIR)" "$(CURDIR)" "$$source" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$$source" "$(CURDIR)" "$$object" >> compile_commands.json; \
	done; printf '\n]\n' >> compile_commands.json

clean:
	rm -rf $(BUILD_DIR) compile_commands.json
