#include "store/catalog.hpp"

#include "catalog_detail.hpp"

#include <algorithm>
#include <utility>

namespace store {

Catalog::Catalog(std::shared_ptr<const LabelPolicy> policy) : policy_(std::move(policy)) {}

void Catalog::add(Item item) {
    item.name = detail::normalize(std::move(item.name));
    items_.add(std::move(item));
}

const Item* Catalog::find(int id) const {
    const auto& values = items_.values();
    const auto found = std::find_if(values.begin(), values.end(), [id](const Item& item) {
        return item.id == id;
    });
    return found == values.end() ? nullptr : &*found;
}

const Item* Catalog::find(std::string_view name) const {
    const auto& values = items_.values();
    const auto found = std::find_if(values.begin(), values.end(), [name](const Item& item) {
        return item.name == name;
    });
    return found == values.end() ? nullptr : &*found;
}

std::string Catalog::label(int id) const {
    const Item* item = find(id);
    return item == nullptr ? std::string{"missing"} : policy_->label(*item);
}

}  // namespace store
