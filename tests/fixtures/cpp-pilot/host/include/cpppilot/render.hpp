#ifndef CPPPILOT_RENDER_HPP
#define CPPPILOT_RENDER_HPP

#include <sstream>
#include <string>
#include <utility>

namespace cpppilot {

template <typename... Parts>
[[nodiscard]] std::string join_parts(Parts&&... parts)
{
    std::ostringstream output;
    ((output << std::forward<Parts>(parts)), ...);
    return output.str();
}

}  // namespace cpppilot

#endif
