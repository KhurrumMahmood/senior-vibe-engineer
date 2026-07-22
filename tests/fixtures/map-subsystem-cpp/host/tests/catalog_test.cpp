#include "store/catalog.hpp"

#include <cassert>
#include <memory>

namespace {

class TestPolicy final : public store::LabelPolicy {
public:
    std::string label(const store::Item& item) const override { return item.name; }
};

}  // namespace

int main() {
    store::Catalog catalog{std::make_shared<TestPolicy>()};
    catalog.add({3, "test"});
    assert(catalog.find(3) != nullptr);
}
