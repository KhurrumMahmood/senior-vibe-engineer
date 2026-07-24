CXX = clang++
CPPFLAGS = -I$(CURDIR)/include -I$(CURDIR)/src
CXXFLAGS = -std=c++20 -Wall -Wextra -Werror -pedantic
BUILD_DIR = .native-build
SOURCES = src/main.cpp src/billing_parser.cpp src/billing_types.cc src/billing_validator.cxx src/syntax.cpp src/omnibus.cpp
OBJECTS = $(BUILD_DIR)/main.o $(BUILD_DIR)/billing_parser.o $(BUILD_DIR)/billing_types.o $(BUILD_DIR)/billing_validator.o $(BUILD_DIR)/syntax.o $(BUILD_DIR)/omnibus.o

.PHONY: all clean compile-db test

all: $(BUILD_DIR)/cpp-cohort-smoke

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/main.o: src/main.cpp include/cohort/billing.hpp include/cohort/detail.tpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/main.cpp -o $@

$(BUILD_DIR)/billing_parser.o: src/billing_parser.cpp include/cohort/billing.hpp include/cohort/detail.tpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/billing_parser.cpp -o $@

$(BUILD_DIR)/billing_types.o: src/billing_types.cc include/cohort/billing.hpp include/cohort/detail.tpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/billing_types.cc -o $@

$(BUILD_DIR)/billing_validator.o: src/billing_validator.cxx include/cohort/billing.hpp include/cohort/detail.tpp src/internal.h | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/billing_validator.cxx -o $@

$(BUILD_DIR)/syntax.o: src/syntax.cpp include/cohort/billing.hpp include/cohort/detail.tpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/syntax.cpp -o $@

$(BUILD_DIR)/omnibus.o: src/omnibus.cpp include/cohort/billing.hpp include/cohort/detail.tpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/omnibus.cpp -o $@

$(BUILD_DIR)/cpp-cohort-smoke: $(OBJECTS)
	$(CXX) $(CXXFLAGS) $(OBJECTS) -o $@

test: $(BUILD_DIR)/cpp-cohort-smoke
	@test "$$($(BUILD_DIR)/cpp-cohort-smoke)" = "cpp-cohort:10:6"
	@printf '%s\n' 'cpp-native-test:ok'

compile-db: | $(BUILD_DIR)
	@printf '[\n  {"directory":"%s","file":"%s/src/main.cpp","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-c","%s/src/main.cpp","-o","%s/.native-build/main.o"]},\n  {"directory":"%s","file":"%s/src/billing_parser.cpp","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-c","%s/src/billing_parser.cpp","-o","%s/.native-build/billing_parser.o"]},\n  {"directory":"%s","file":"%s/src/billing_types.cc","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-c","%s/src/billing_types.cc","-o","%s/.native-build/billing_types.o"]},\n  {"directory":"%s","file":"%s/src/billing_validator.cxx","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-c","%s/src/billing_validator.cxx","-o","%s/.native-build/billing_validator.o"]},\n  {"directory":"%s","file":"%s/src/syntax.cpp","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-c","%s/src/syntax.cpp","-o","%s/.native-build/syntax.o"]},\n  {"directory":"%s","file":"%s/src/omnibus.cpp","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-c","%s/src/omnibus.cpp","-o","%s/.native-build/omnibus.o"]}\n]\n' "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" > compile_commands.json

clean:
	rm -rf $(BUILD_DIR) compile_commands.json
