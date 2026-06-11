# scenario-plan-dropout

A multi-item plan declares three workstreams. The ledger has intakes for
two of them. The third is the dropped item.

`find_plan_dropouts` should return only the dropped item; the present
items match by id or title-token equality.
