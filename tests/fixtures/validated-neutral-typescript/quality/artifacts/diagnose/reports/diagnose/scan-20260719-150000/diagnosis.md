# Diagnosis: queue retry contract rejects a synchronous delay

## Symptom

The queue adapter cannot accept the retry function as its asynchronous delay
provider.

## Reproduction

`npx tsc --noEmit --strict diagnostics/retry-contract.ts` fails with TS2322.

## Root cause

`src/worker/retry.ts::retryDelay` returns `number`, while the queue adapter
boundary asks for `(attempt) => Promise<number>`.

## Fix

No source change was made during diagnosis. Decide whether the adapter should
wrap the synchronous policy or the policy should become asynchronous.

## Prevention follow-up

Keep a boundary contract check at the queue adapter seam.
