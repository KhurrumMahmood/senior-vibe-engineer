#ifndef STORE_CATALOG_DETAIL_HPP
#define STORE_CATALOG_DETAIL_HPP

#include <string>

namespace store::detail {

[[nodiscard]] inline std::string normalize(std::string value) {
    return value.empty() ? std::string{"unnamed"} : value;
}

}  // namespace store::detail

#endif
