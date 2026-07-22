#ifndef STORE_QUERY_HPP
#define STORE_QUERY_HPP

#include <string>

namespace store {

class Catalog;

[[nodiscard]] std::string describe_item(const Catalog& catalog, int id);

}  // namespace store

#endif
