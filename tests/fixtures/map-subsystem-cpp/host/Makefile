CXX = clang++
AR = ar
CPPFLAGS = -I$(CURDIR)/include -I$(CURDIR)/src -DSTORE_FEATURE=1
CXXFLAGS = -std=c++20 -Wall -Wextra -Werror -pedantic
BUILD_DIR = .native-build
LIB_OBJECTS = $(BUILD_DIR)/catalog.o $(BUILD_DIR)/query.o

.PHONY: all clean compile-db test

all: $(BUILD_DIR)/store-demo

$(BUILD_DIR):
	mkdir -p $@

$(BUILD_DIR)/catalog.o: src/catalog.cpp include/store/catalog.hpp include/store/labels.tpp src/catalog_detail.hpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/catalog.cpp -o $@

$(BUILD_DIR)/query.o: src/query.cpp include/store/catalog.hpp include/store/query.hpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/src/query.cpp -o $@

$(BUILD_DIR)/demo.o: apps/demo.cpp include/store/catalog.hpp include/store/query.hpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $(CURDIR)/apps/demo.cpp -o $@

$(BUILD_DIR)/libstore.a: $(LIB_OBJECTS)
	$(AR) rcs $@ $^

$(BUILD_DIR)/store-demo: $(BUILD_DIR)/demo.o $(BUILD_DIR)/libstore.a
	$(CXX) $(CXXFLAGS) $^ -o $@

$(BUILD_DIR)/catalog-test: tests/catalog_test.cpp $(BUILD_DIR)/libstore.a | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) $< $(BUILD_DIR)/libstore.a -o $@

test: $(BUILD_DIR)/store-demo $(BUILD_DIR)/catalog-test
	@test "$$($(BUILD_DIR)/store-demo)" = "book:book:book"
	@$(BUILD_DIR)/catalog-test

compile-db:
	@printf '[\n  {"directory":"%s","file":"%s/src/catalog.cpp","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-DSTORE_FEATURE=1","-c","%s/src/catalog.cpp","-o","%s/.native-build/catalog.o"]},\n  {"directory":"%s","file":"%s/src/query.cpp","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-DSTORE_FEATURE=1","-c","%s/src/query.cpp","-o","%s/.native-build/query.o"]},\n  {"directory":"%s","file":"%s/apps/demo.cpp","arguments":["%s","-std=c++20","-Wall","-Wextra","-Werror","-pedantic","-I%s/include","-I%s/src","-DSTORE_FEATURE=1","-c","%s/apps/demo.cpp","-o","%s/.native-build/demo.o"]}\n]\n' "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CXX)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" "$(CURDIR)" > compile_commands.json

clean:
	rm -rf $(BUILD_DIR) compile_commands.json
