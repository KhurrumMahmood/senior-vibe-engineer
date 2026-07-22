# Java 17 v1: compiler-resolved subpackage proposals

Read this reference only for a Java folder-reorganization proposal.

## Contract

V1 accepts two explicit human judgments: the filename cluster is a real
conceptual split, and this project permits the proposed Java subpackage. It
does not infer framework or build-tool conventions. The helper then uses the
host JDK compiler, tree, and type APIs to inspect one conventional source root
containing three or more direct `<Prefix>*.java` siblings.

The result is a read-only move plan with package declarations, compiler-
resolved imports, static imports, fully-qualified type uses, wildcard review,
and same-package references that need imports after the split. Package-private
cross-boundary access, matching identities under generated/test/vendor/build
trees, unsafe paths, malformed or unresolved source, mixed package topology,
an existing destination, and missing or old JDK tools block the proposal.

V1 deliberately does not load Maven, Gradle, JARs, external source roots,
annotation processors, or framework metadata. A `ready` result therefore
means the current source root is internally resolved and safe to hand to a
human; it is not permission to edit files.

## Installed command

Run from the target Java project root after copying this selected skill. Both
`java` and `javac` must be JDK 17 or newer on `PATH`. The command writes only
the two report artifacts.

<!-- installed-command:java-proposal:start -->
```bash
PFR_PARENT="${PFR_PARENT:-src/main/java/example/legacy}"
PFR_PREFIX="${PFR_PREFIX:-billing}"
PFR_CLUSTER_JUDGMENT="${PFR_CLUSTER_JUDGMENT:-split}"
PFR_CONVENTION_JUDGMENT="${PFR_CONVENTION_JUDGMENT:-approve-subpackage}"
PFR_NAME="${PFR_NAME:-${PFR_PARENT//\//-}__${PFR_PREFIX}}"
PFR_MINIMUM_JDK="${PFR_MINIMUM_JDK:-17}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/propose-folder-reorganization" \
  ".agents/skills/propose-folder-reorganization" \
  ".claude/skills/propose-folder-reorganization"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "propose-folder-reorganization is not available" >&2
  exit 2
fi
REPORT_ROOT="reports/propose-folder-reorganization/${PFR_NAME}"
python3 -I -S "${SKILL_ROOT}/scripts/propose_java.py" \
  --parent "${PFR_PARENT}" \
  --prefix "${PFR_PREFIX}" \
  --cluster-judgment "${PFR_CLUSTER_JUDGMENT}" \
  --convention-judgment "${PFR_CONVENTION_JUDGMENT}" \
  --project-root "$(pwd)" \
  --minimum-jdk "${PFR_MINIMUM_JDK}" \
  --inspection "${REPORT_ROOT}/inspection.json" \
  --proposal "${REPORT_ROOT}/proposal.md"
```
<!-- installed-command:java-proposal:end -->

## Human handoff

Treat `ready` as scoped evidence, not execution authority. Before a separately
reviewed move, record the project's native `javac`/build and test commands.
After the move, run those commands and re-run this proposal if any source or
human judgment changes.
