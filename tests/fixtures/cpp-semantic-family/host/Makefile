CXX = clang++
CPPFLAGS = -I$(CURDIR)/include
CXXFLAGS = -std=c++20 -Wall -Wextra -Werror -pedantic
BUILD_DIR = .native-build
SOURCES = src/semantic.cpp src/report_alpha.cpp src/report_beta.cpp src/report_gamma.cpp src/main.cpp
OBJECTS = $(SOURCES:src/%.cpp=$(BUILD_DIR)/%.o)

.PHONY: all clean compile-db test

all: $(BUILD_DIR)/cpp-semantic-smoke

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/%.o: src/%.cpp include/cppsemantic/semantic.hpp | $(BUILD_DIR)
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/$< -o $@

$(BUILD_DIR)/cpp-semantic-smoke: $(OBJECTS)
	$(CXX) $(CXXFLAGS) $(OBJECTS) -o $@

test: $(BUILD_DIR)/cpp-semantic-smoke
	@test "$$($(BUILD_DIR)/cpp-semantic-smoke)" = "cpp-semantic:running:us:112:1:LegacyStatus:41"

compile-db: | $(BUILD_DIR)
	@$(MAKE) --no-print-directory emit-compile-db | sed '$$s/,$$//' | { printf '[\n'; cat; printf ']\n'; } > compile_commands.json

.PHONY: emit-compile-db
emit-compile-db:
	@$(foreach source,$(SOURCES),printf '  {"directory":"%s","file":"%s/$(source)","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-c","%s/$(source)","-o","%s/$(BUILD_DIR)/$(notdir $(source:.cpp=.o))"]},\n' "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)";)

clean:
	rm -rf $(BUILD_DIR) compile_commands.json
