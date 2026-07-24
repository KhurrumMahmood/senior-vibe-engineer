#include "cppsemantic/semantic.hpp"

namespace cppsemantic::reports {
namespace {

int gamma_value()
{
    return identity(17);
}

}  // namespace

int gamma_report()
{
    return gamma_value();
}

}  // namespace cppsemantic::reports
