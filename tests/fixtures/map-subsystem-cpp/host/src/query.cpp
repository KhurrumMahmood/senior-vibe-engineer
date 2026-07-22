#include "store/query.hpp"

#include "store/catalog.hpp"

namespace store {

std::string describe_item(const Catalog& catalog, int id) {
    const Item* item = catalog.find(id);
    return item == nullptr ? std::string{"missing"} : label_for(*item);
}

}  // namespace store
