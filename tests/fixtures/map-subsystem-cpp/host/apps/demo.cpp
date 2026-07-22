#include "store/catalog.hpp"
#include "store/query.hpp"

#include <iostream>
#include <memory>

namespace {

class NamePolicy final : public store::LabelPolicy {
public:
    std::string label(const store::Item& item) const override { return item.name; }
};

}  // namespace

int main() {
    store::Catalog catalog{std::make_shared<NamePolicy>()};
    catalog.add({7, "book"});
    std::cout << catalog.label(7) << ':' << store::describe_item(catalog, 7) << ':'
              << catalog.find("book")->name << '\n';
}
