# scenario-supersession-chain

Three ideas form a chain: idea-a → idea-b → idea-c.

idea-a is `done/superseded` with `superseded_by: idea-b`. idea-b is
also `done/superseded` with `superseded_by: idea-c`. idea-c is
in-flight (the current best version of the lineage).

`supersession_chain(records, "idea-a")` should return the full chain
in order.

A second test would walk from idea-b (returning the tail); this fixture
asserts the head-of-chain case.
