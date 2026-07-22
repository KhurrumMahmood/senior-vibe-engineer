#ifndef CPPPILOT_INVOICE_DETAIL_HPP
#define CPPPILOT_INVOICE_DETAIL_HPP

#include <string_view>

// Keep mode selection compile-time so shipped binaries expose no mutable flag.
constexpr std::string_view invoice_mode()
{
#if CPP_PILOT_MODE
    return "pilot";
#else
    return "standard";
#endif
}

#endif
