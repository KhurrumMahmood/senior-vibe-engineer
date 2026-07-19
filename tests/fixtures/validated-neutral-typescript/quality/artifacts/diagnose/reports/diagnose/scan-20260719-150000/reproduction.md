# Reproduction

Command:

```text
npx tsc --noEmit --strict diagnostics/retry-contract.ts
```

Observed output:

```text
diagnostics/retry-contract.ts(3,7): error TS2322: Type '(attempt: number) => number' is not assignable to type '(attempt: number) => Promise<number>'.
```
