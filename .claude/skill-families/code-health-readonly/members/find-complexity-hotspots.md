# Complexity lens

Purpose: report syntactic high-branch TypeScript/JavaScript functions as
investigation leads. It does not resolve types, call graphs, framework
semantics, runtime frequency, or data size.

The launcher runs the on-demand
`find-complexity-hotspots/scripts/run.py` with the explicit language, project
root, target, and no toolkit telemetry. Read
`reports/find-complexity-hotspots/latest/findings.json` as the final artifact.
Missing native tooling, malformed eligible source, missing artifacts, or
unsupported matched content is a failed/incomplete lane, not zero findings.
Generated, vendor, dependency, test/spec, declaration, minified, build-output,
and symlink paths stay excluded. This lane is read-only outside its report
directory; a high score alone never authorizes optimization.
