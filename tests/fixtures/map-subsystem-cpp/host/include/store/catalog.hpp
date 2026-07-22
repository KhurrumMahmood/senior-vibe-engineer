#ifndef STORE_CATALOG_HPP
#define STORE_CATALOG_HPP

#include <memory>
#include <string>
#include <string_view>
#include <vector>

namespace store {

struct Item {
    int id;
    std::string name;
};

class LabelPolicy {
public:
    virtual ~LabelPolicy() = default;
    [[nodiscard]] virtual std::string label(const Item& item) const = 0;
};

template <typename T>
class Repository {
public:
    void add(T value) { values_.push_back(std::move(value)); }
    [[nodiscard]] const std::vector<T>& values() const { return values_; }

private:
    std::vector<T> values_;
};

class Catalog {
public:
    explicit Catalog(std::shared_ptr<const LabelPolicy> policy);
    void add(Item item);
    [[nodiscard]] const Item* find(int id) const;
    [[nodiscard]] const Item* find(std::string_view name) const;
    [[nodiscard]] std::string label(int id) const;

private:
    Repository<Item> items_;
    std::shared_ptr<const LabelPolicy> policy_;
};

template <typename T>
[[nodiscard]] std::string label_for(const T& value);

}  // namespace store

#include "store/labels.tpp"

#endif
