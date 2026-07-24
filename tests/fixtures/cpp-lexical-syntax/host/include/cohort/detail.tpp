#ifndef COHORT_DETAIL_TPP
#define COHORT_DETAIL_TPP

namespace cohort {

template <typename T>
int label_for(const T& value)
{
    return value.id;
}

}  // namespace cohort

#endif
