#include "legacy.hpp"

namespace cppproposal {

int load_credentials() { return 1; }
int rotate_credentials() { return 2; }
int authorize_admin() { return 3; }
int validate_admin() { return 4; }
int render_export(int value) { return value + 5; }
int render_export(std::string_view value) { return static_cast<int>(value.size()) + 5; }
int write_export() { return 6; }
int save_invoice() { return 7; }
int load_invoice() { return 8; }

}  // namespace cppproposal
