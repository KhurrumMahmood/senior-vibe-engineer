# scenario-harvest-ready

An idea was partially harvested — done with `outcome=harvested` — but
the captor flagged `has-more-potential`, signaling that remaining
capacity is meaningful.

A second idea is in-flight with the same marker; it should NOT be
returned (it's actively being worked on, not a harvest opportunity).

A third idea is done/adopted with no marker; should also not appear.

`find_harvest_opportunities` should return only the first.
