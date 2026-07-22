# Root cause

Hypothesis confirmed: the queue adapter expects Promise<number>, but
`src/worker/retry.ts::retryDelay` returns a synchronous number.

Confirming probe:

```text
npx tsc --noEmit --strict diagnostics/retry-contract.ts
diagnostics/retry-contract.ts(3,7): error TS2322: Type '(attempt: number) => number' is not assignable to type '(attempt: number) => Promise<number>'.
```

Class lift: grep for `Promise<number>` across adapter contracts before changing
the policy. The diagnosis made no source change, so this is a seam finding, not
a verified source fix.
