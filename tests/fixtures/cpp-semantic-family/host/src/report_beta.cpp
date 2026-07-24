#include "cppsemantic/semantic.hpp"

namespace cppsemantic::reports {
namespace {

int beta_value()
{
    return identity(13);
}

}  // namespace

int beta_report()
{
    return beta_value();
}

}  // namespace cppsemantic::reports
