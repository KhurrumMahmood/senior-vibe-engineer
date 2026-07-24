#ifndef CPP_STRUCTURE_LEGACY_HPP
#define CPP_STRUCTURE_LEGACY_HPP

#include <string_view>

namespace cppproposal {

int load_credentials();
int rotate_credentials();
int authorize_admin();
int validate_admin();
int render_export(int value);
int render_export(std::string_view value);
int write_export();
int save_invoice();
int load_invoice();

}  // namespace cppproposal

#endif
