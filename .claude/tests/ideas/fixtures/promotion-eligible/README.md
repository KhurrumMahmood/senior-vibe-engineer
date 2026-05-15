# scenario-promotion-eligible

Three ideas:
- `single-adoption`: in-flight with one adoption event → eligible at
  `single-constraint-set` qualifier
- `triple-adoption`: done/adopted with three adoption events →
  eligible at `validated-across-N`
- `no-adoption`: in-flight with no adoption events → NOT eligible
- `rejected-with-adoption`: done/rejected but somehow has an
  adoption_evidence (data error path; eligibility is gated by outcome,
  so should not be returned)

`promotion_eligible` should return the first two, sorted by id.
