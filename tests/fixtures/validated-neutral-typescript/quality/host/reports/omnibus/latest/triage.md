# Omnibus triage

## Confirmed findings

- `omnibus-001`: `src/worker/retry.ts` owns scheduling, transport retries,
  and dashboard formatting in the same change set. Split the ownership before
  adding another caller.
