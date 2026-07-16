---
name: portable-planner
description: Plan a framework-neutral change from evidence.
argument-hint: "<goal>"
allowed-tools: Read
user-invocable: true
tier: feature
job: plan
best_for: Planning a change without assuming a host stack.
not_for: Framework-native implementation details.
language: any
framework: any
---

# Portable planner

Inspect the host profile, preserve the existing behavior, and record the
verification command before implementation begins.

```text
framework-specific commands come from the selected binding
```
