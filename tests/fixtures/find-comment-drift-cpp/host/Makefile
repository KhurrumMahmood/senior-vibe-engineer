CXX = clang++
CPPFLAGS = -I$(CURDIR)/include -I$(CURDIR)/src -DCPP_PILOT_MODE=1
CXXFLAGS = -std=c++20 -Wall -Wextra -Werror -pedantic
BUILD_DIR = .native-build
SOURCES = src/invoice.cpp src/main.cpp src/roles.cc src/ledger.cxx
OBJECTS = $(BUILD_DIR)/invoice.o $(BUILD_DIR)/main.o $(BUILD_DIR)/roles.o $(BUILD_DIR)/ledger.o

.PHONY: all clean compile-db test

all: $(BUILD_DIR)/cpp-comment-smoke

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/invoice.o: src/invoice.cpp include/cpppilot/invoice.hpp src/common.h src/format_support.inl src/invoice_detail.hpp src/invoice_format.ipp include/cpppilot/identity.tpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/invoice.cpp -o $@

$(BUILD_DIR)/main.o: src/main.cpp include/cpppilot/invoice.hpp include/cpppilot/identity.tpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/main.cpp -o $@

$(BUILD_DIR)/roles.o: src/roles.cc include/cpppilot/roles.hh | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/roles.cc -o $@

$(BUILD_DIR)/ledger.o: src/ledger.cxx include/cpppilot/ledger.hxx | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/ledger.cxx -o $@

$(BUILD_DIR)/cpp-comment-smoke: $(OBJECTS)
	$(CXX) $(CXXFLAGS) $(OBJECTS) -o $@

test: $(BUILD_DIR)/cpp-comment-smoke
	@test "$$($(BUILD_DIR)/cpp-comment-smoke)" = "invoice:INV-42:pilot:42:3"

compile-db: | $(BUILD_DIR)
	@printf '[\n  {"directory":"%s","file":"%s/src/invoice.cpp","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-DCPP_PILOT_MODE=1","-c","%s/src/invoice.cpp","-o","%s/.native-build/invoice.o"]},\n  {"directory":"%s","file":"%s/src/main.cpp","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-DCPP_PILOT_MODE=1","-c","%s/src/main.cpp","-o","%s/.native-build/main.o"]},\n  {"directory":"%s","file":"%s/src/roles.cc","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-DCPP_PILOT_MODE=1","-c","%s/src/roles.cc","-o","%s/.native-build/roles.o"]},\n  {"directory":"%s","file":"%s/src/ledger.cxx","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-DCPP_PILOT_MODE=1","-c","%s/src/ledger.cxx","-o","%s/.native-build/ledger.o"]}\n]\n' "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" > compile_commands.json

clean:
	rm -rf $(BUILD_DIR) compile_commands.json
