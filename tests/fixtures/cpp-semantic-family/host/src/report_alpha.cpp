#include "cppsemantic/semantic.hpp"

namespace cppsemantic::reports {
namespace {

int alpha_value()
{
    return identity(11);
}

}  // namespace

int alpha_report()
{
    return alpha_value();
}

}  // namespace cppsemantic::reports
