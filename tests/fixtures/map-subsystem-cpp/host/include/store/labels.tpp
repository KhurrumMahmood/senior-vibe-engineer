#ifndef STORE_LABELS_TPP
#define STORE_LABELS_TPP

#include <string>

namespace store {

template <typename T>
std::string label_for(const T& value) {
    return value.name;
}

}  // namespace store

#endif
