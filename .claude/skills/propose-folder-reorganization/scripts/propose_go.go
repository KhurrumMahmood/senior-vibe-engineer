// Produce one conservative, read-only Go folder-reorganization proposal.
//
// The helper uses the host Go toolchain and standard library only. It treats a
// filename cluster as evidence, not authority: a project convention must opt
// into the new package boundary, and language-safety blockers still win.
package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"go/ast"
	"go/importer"
	"go/parser"
	"go/token"
	"go/types"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"unicode"
)

const defaultMinimumGo = "1.22"

type moduleInfo struct {
	Path      string `json:"Path"`
	Dir       string `json:"Dir"`
	GoVersion string `json:"GoVersion"`
}

type packageError struct {
	Err string `json:"Err"`
}

type packageInfo struct {
	Dir            string            `json:"Dir"`
	ImportPath     string            `json:"ImportPath"`
	ForTest        string            `json:"ForTest"`
	Name           string            `json:"Name"`
	GoFiles        []string          `json:"GoFiles"`
	CgoFiles       []string          `json:"CgoFiles"`
	IgnoredGoFiles []string          `json:"IgnoredGoFiles"`
	TestGoFiles    []string          `json:"TestGoFiles"`
	XTestGoFiles   []string          `json:"XTestGoFiles"`
	Export         string            `json:"Export"`
	ImportMap      map[string]string `json:"ImportMap"`
	Incomplete     bool              `json:"Incomplete"`
	Error          *packageError     `json:"Error"`
}

type conventionRule struct {
	Parent      string `json:"parent"`
	Prefix      string `json:"prefix"`
	Action      string `json:"action"`
	Destination string `json:"destination,omitempty"`
	Rationale   string `json:"rationale"`
}

type conventionProfile struct {
	SchemaVersion int              `json:"schema_version"`
	Rules         []conventionRule `json:"rules"`
}

type conventionEvidence struct {
	Source                 string           `json:"source"`
	Precedence             []string         `json:"precedence"`
	AppliedRules           []conventionRule `json:"applied_rules"`
	DetectedFrameworkRules []string         `json:"detected_framework_rules"`
	LanguageConstraints    []string         `json:"language_constraints"`
	GenericHeuristics      []string         `json:"generic_heuristics"`
	Conflicts              []string         `json:"conflicts"`
	UnresolvedAssumptions  []string         `json:"unresolved_assumptions"`
}

type moveFile struct {
	CurrentPath   string `json:"current_path"`
	NewPath       string `json:"new_path"`
	PackageBefore string `json:"package_before"`
	PackageAfter  string `json:"package_after"`
}

type importImpact struct {
	Importer         string `json:"importer"`
	Line             int    `json:"line"`
	CurrentImport    string `json:"current_import_path"`
	AfterImport      string `json:"after_import_path"`
	CurrentQualifier string `json:"current_qualifier"`
	AfterQualifier   string `json:"after_qualifier"`
	Symbol           string `json:"symbol"`
	Kind             string `json:"kind"`
}

type crossReference struct {
	File       string `json:"file"`
	Line       int    `json:"line"`
	Symbol     string `json:"symbol"`
	DeclaredIn string `json:"declared_in"`
	Exported   bool   `json:"exported"`
	Direction  string `json:"direction"`
}

type parsedSource struct {
	Path string
	AST  *ast.File
}

type declaration struct {
	Name     string
	Path     string
	Selected bool
	Exported bool
}

type runnerError struct {
	message string
	exit    int
}

func (err *runnerError) Error() string { return err.message }

func main() {
	var parent, prefix, judgment, projectRoot, conventions, inspection, proposal, minimumGo string
	flag.StringVar(&parent, "parent", "", "parent package directory inside the project")
	flag.StringVar(&prefix, "prefix", "", "confirmed filename prefix")
	flag.StringVar(&judgment, "cluster-judgment", "", "split or cohesive")
	flag.StringVar(&projectRoot, "project-root", ".", "host project root")
	flag.StringVar(&conventions, "conventions", "", "optional project convention JSON")
	flag.StringVar(&inspection, "inspection", "", "inspection JSON path")
	flag.StringVar(&proposal, "proposal", "", "proposal Markdown path")
	flag.StringVar(&minimumGo, "minimum-go", defaultMinimumGo, "minimum Go toolchain")
	flag.Parse()
	if parent == "" || prefix == "" || inspection == "" || proposal == "" || (judgment != "split" && judgment != "cohesive") {
		fmt.Fprintln(os.Stderr, "usage: propose_go.go --parent <dir> --prefix <token> --cluster-judgment <split|cohesive> --project-root <dir> [--conventions <json>] --inspection <path> --proposal <path>")
		os.Exit(2)
	}
	if !validPrefix(prefix) {
		fmt.Fprintln(os.Stderr, "prefix must be a filename domain token")
		os.Exit(2)
	}
	root, err := filepath.Abs(projectRoot)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	root = filepath.Clean(root)
	inspectionPath, err := artifactPath(root, inspection)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	proposalPath, err := artifactPath(root, proposal)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	if runErr := run(root, parent, prefix, judgment, conventions, inspectionPath, proposalPath, minimumGo); runErr != nil {
		fmt.Fprintln(os.Stderr, runErr.message)
		if runErr.exit != 0 {
			os.Exit(runErr.exit)
		}
	}
}

func run(root, parent, prefix, judgment, conventionArg, inspection, proposal, minimumGo string) *runnerError {
	base := basePayload(parent, prefix)
	goPath, err := exec.LookPath("go")
	if err != nil {
		return writeTerminal(base, inspection, proposal, "unsupported", "defer_tool_missing", "go_tool_missing", "Go was not found on PATH.", 0)
	}
	versionText, err := commandOutput(root, goPath, "version")
	if err != nil {
		return writeTerminal(base, inspection, proposal, "unsupported", "defer_tool_unavailable", "go_version_failed", err.Error(), 0)
	}
	version := strings.TrimSpace(strings.TrimPrefix(versionText, "go version "))
	base["tooling"] = map[string]interface{}{"go_path": goPath, "go_version": version, "minimum_go": minimumGo, "parser": "go/parser and go/types (standard library)"}
	if !atLeastGoVersion(version, minimumGo) {
		return writeTerminal(base, inspection, proposal, "unsupported", "defer_go_version", "go_version_too_old", fmt.Sprintf("Go %s is below required Go %s.", version, minimumGo), 0)
	}
	workspace, err := commandOutput(root, goPath, "env", "GOWORK")
	if err != nil || (strings.TrimSpace(workspace) != "" && strings.TrimSpace(workspace) != "off") {
		return writeTerminal(base, inspection, proposal, "unsupported", "defer_workspace", "go_workspace_active", "Go v1 requires a single module with no active go.work workspace.", 0)
	}
	module, err := moduleFacts(root, goPath)
	if err != nil || module.Path == "" || clean(module.Dir) != clean(root) {
		message := "A Go module rooted at the project is required."
		if err != nil {
			message = err.Error()
		}
		return writeTerminal(base, inspection, proposal, "unsupported", "defer_not_go_module", "go_module_required", message, 0)
	}
	base["module"] = map[string]interface{}{"path": module.Path, "go_version": module.GoVersion}
	if nested := nestedModules(root); len(nested) > 0 {
		base["nested_modules"] = nested
		return writeTerminal(base, inspection, proposal, "unsupported", "defer_module_topology", "nested_modules", "Nested Go modules fall outside the single-module impact boundary.", 0)
	}

	parentPath, err := projectPath(root, parent)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return &runnerError{message: err.Error(), exit: 2}
	}
	info, err := os.Stat(parentPath)
	if err != nil || !info.IsDir() {
		return writeTerminal(base, inspection, proposal, "unsupported", "defer_target_not_found", "target_not_found", "Parent must be an existing project directory.", 0)
	}
	if !internalPackagePath(filepath.ToSlash(parent)) {
		return writeTerminal(base, inspection, proposal, "blocked", "defer_external_subpath_compatibility", "external_subpath_unknown", "Go v1 only proposes internal package splits; external consumers of a public package cannot be enumerated from this module.", 0)
	}
	packageAfter := prefixPackage(prefix)
	if packageAfter == "" || token.Lookup(packageAfter).IsKeyword() {
		return writeTerminal(base, inspection, proposal, "blocked", "defer_invalid_package_name", "invalid_package_name", "The prefix does not produce a valid non-keyword Go package name.", 0)
	}
	destinationPath := filepath.Join(parentPath, prefix)
	if _, statErr := os.Lstat(destinationPath); statErr == nil {
		return writeTerminal(base, inspection, proposal, "blocked", "defer_destination_exists", "destination_exists", "The proposed package destination already exists; merge semantics are outside bounded v1.", 0)
	} else if !os.IsNotExist(statErr) {
		return writeTerminal(base, inspection, proposal, "failed", "defer_destination_unreadable", "destination_unreadable", statErr.Error(), 2)
	}
	if risks, riskErr := clusterFilesystemRisks(root, parentPath, prefix); riskErr != nil {
		return writeTerminal(base, inspection, proposal, "failed", "defer_target_unreadable", "target_unreadable", riskErr.Error(), 2)
	} else if len(risks) > 0 {
		base["filesystem_risks"] = risks
		return writeTerminal(base, inspection, proposal, "partial", "defer_unsafe_or_generated_cluster", "unsafe_or_generated_cluster", "Generated or symlinked cluster members prevent a complete move plan.", 0)
	}

	convention, conventionErr := loadConventions(root, conventionArg, parent, prefix)
	if conventionErr != nil {
		base["conventions"] = convention
		return writeTerminal(base, inspection, proposal, "failed", "defer_invalid_conventions", "invalid_conventions", conventionErr.Error(), 2)
	}
	base["conventions"] = convention

	packages, listErr := packageFacts(root, goPath)
	if listErr != nil {
		return writeTerminal(base, inspection, proposal, "partial", "defer_unresolved_package_graph", "go_list_failed", listErr.Error(), 0)
	}
	var target *packageInfo
	for index := range packages {
		if clean(packages[index].Dir) == clean(parentPath) && packages[index].ForTest == "" && !strings.HasSuffix(packages[index].ImportPath, ".test") {
			target = &packages[index]
			break
		}
	}
	if target == nil || target.ImportPath == "" {
		return writeTerminal(base, inspection, proposal, "partial", "defer_unresolved_package_graph", "target_package_unresolved", "go list could not establish the target package.", 0)
	}
	base["target"] = map[string]interface{}{"parent": filepath.ToSlash(parent), "prefix": prefix, "package": target.Name, "import_path": target.ImportPath}

	cluster, tests, selectedSet, parseSources, scanErr := inspectTarget(root, parentPath, parent, prefix, target)
	if scanErr != nil {
		return writeTerminal(base, inspection, proposal, "failed", "defer_syntax_error", "syntax_error", scanErr.Error(), 2)
	}
	base["cluster_files"] = cluster
	base["test_files"] = tests
	if len(cluster) < 3 {
		base["summary"] = summary(len(cluster), len(tests), 0, 0)
		return writeTerminal(base, inspection, proposal, "deferred", "defer_below_threshold", "cluster_below_threshold", "The confirmed cluster has fewer than three eligible production siblings.", 0)
	}
	if judgment == "cohesive" {
		base["summary"] = summary(len(cluster), len(tests), 0, 0)
		return writeTerminal(base, inspection, proposal, "deferred", "defer_cohesive_cluster", "cohesive_cluster", "The human judgment says the flat cluster is deliberately cohesive.", 0)
	}
	for _, name := range target.IgnoredGoFiles {
		if matchesPrefix(name, prefix) {
			base["summary"] = summary(len(cluster), len(tests), 0, 0)
			base["ignored_cluster_files"] = matchingNames(target.IgnoredGoFiles, prefix)
			return writeTerminal(base, inspection, proposal, "partial", "defer_build_constraints", "build_constraints", "Inactive build-tagged cluster files make this host configuration incomplete.", 0)
		}
	}
	if len(target.CgoFiles) > 0 || len(target.XTestGoFiles) > 0 {
		base["summary"] = summary(len(cluster), len(tests), 0, 0)
		return writeTerminal(base, inspection, proposal, "partial", "defer_build_constraints", "cgo_or_external_tests", "Cgo or external-package tests make the proposed boundary configuration-dependent.", 0)
	}

	cross, initRisks, declarations, typeErr := crossBoundaryFacts(root, target, packages, parseSources, selectedSet)
	if typeErr != nil {
		base["summary"] = summary(len(cluster), len(tests), 0, 0)
		return writeTerminal(base, inspection, proposal, "partial", "defer_unresolved_type_graph", "go_types_failed", typeErr.Error(), 0)
	}
	base["cross_boundary_references"] = cross
	base["initialization_risks"] = initRisks
	if len(cross) > 0 || len(initRisks) > 0 {
		base["summary"] = summary(len(cluster), len(tests), 0, len(cross))
		return writeTerminal(base, inspection, proposal, "blocked", "defer_cross_package_boundary", "cross_package_boundary", "Resolved package-private/cross-boundary references or package initialization semantics prevent a mechanical split.", 0)
	}

	impacts, ambiguities, impactErr := importImpacts(root, packages, target, declarations, filepath.ToSlash(filepath.Join(parent, prefix)))
	if impactErr != nil {
		base["summary"] = summary(len(cluster), len(tests), 0, 0)
		return writeTerminal(base, inspection, proposal, "partial", "defer_unresolved_imports", "import_impact_failed", impactErr.Error(), 0)
	}
	base["import_impact"] = impacts
	base["ambiguous_imports"] = ambiguities
	if len(ambiguities) > 0 {
		base["summary"] = summary(len(cluster), len(tests), len(impacts), 0)
		return writeTerminal(base, inspection, proposal, "blocked", "defer_ambiguous_imports", "ambiguous_imports", "Dot, blank, or unresolved imports prevent complete impact enumeration.", 0)
	}

	allow, deny := conventionActions(convention.AppliedRules)
	if allow && deny {
		convention.Conflicts = append(convention.Conflicts, "matching allow_package_split and deny_package_split rules")
		base["conventions"] = convention
		base["summary"] = summary(len(cluster), len(tests), len(impacts), 0)
		return writeTerminal(base, inspection, proposal, "blocked", "defer_convention_conflict", "convention_conflict", "Project convention rules conflict for this cluster.", 0)
	}
	if !allow {
		if deny {
			base["summary"] = summary(len(cluster), len(tests), len(impacts), 0)
			return writeTerminal(base, inspection, proposal, "deferred", "defer_project_convention", "project_convention_denies", "The project convention keeps this package flat.", 0)
		}
		convention.UnresolvedAssumptions = append(convention.UnresolvedAssumptions, "No explicit or detected convention authorizes a new Go package boundary.")
		base["conventions"] = convention
		base["summary"] = summary(len(cluster), len(tests), len(impacts), 0)
		return writeTerminal(base, inspection, proposal, "deferred", "defer_project_convention_required", "project_convention_required", "The >=3 threshold is evidence of a cluster, not authority for a Go package split.", 0)
	}
	expectedDestination := filepath.ToSlash(filepath.Join(parent, prefix))
	for _, rule := range convention.AppliedRules {
		if rule.Action == "allow_package_split" && filepath.ToSlash(rule.Destination) != expectedDestination {
			convention.Conflicts = append(convention.Conflicts, "allowed destination differs from the bounded v1 destination")
			base["conventions"] = convention
			base["summary"] = summary(len(cluster), len(tests), len(impacts), 0)
			return writeTerminal(base, inspection, proposal, "blocked", "defer_convention_conflict", "destination_conflict", "The project convention destination conflicts with the bounded move shape.", 0)
		}
	}

	base["status"] = "ready"
	base["recommendation"] = "refactor"
	base["message"] = "The explicit project convention authorizes this package boundary and the active Go graph has no bounded-v1 blocker."
	base["summary"] = summary(len(cluster), len(tests), len(impacts), len(cross))
	base["native_verification"] = map[string]interface{}{
		"commands":   []string{"go test ./...", "go vet ./..."},
		"obligation": "Run both commands before and after the human-approved move; preserve source behavior and public API deliberately.",
	}
	base["impact_scope"] = "complete for active and visibly inactive source files in this single Go module; the internal/ boundary excludes external module consumers"
	return writePayload(base, inspection, proposal, 0)
}

func basePayload(parent, prefix string) map[string]interface{} {
	return map[string]interface{}{
		"schema_version":            1,
		"skill":                     "propose-folder-reorganization",
		"language":                  "go",
		"analyzer":                  "go-list-plus-stdlib-types",
		"target":                    map[string]interface{}{"parent": filepath.ToSlash(parent), "prefix": prefix},
		"cluster_files":             []moveFile{},
		"test_files":                []moveFile{},
		"import_impact":             []importImpact{},
		"cross_boundary_references": []crossReference{},
		"initialization_risks":      []string{},
		"ambiguous_imports":         []string{},
		"native_verification":       map[string]interface{}{"commands": []string{"go test ./...", "go vet ./..."}},
	}
}

func summary(cluster, tests, impacts, cross int) map[string]interface{} {
	return map[string]interface{}{
		"cluster_size":                   cluster,
		"test_file_count":                tests,
		"resolved_import_impact_count":   impacts,
		"cross_boundary_reference_count": cross,
	}
}

func writeTerminal(payload map[string]interface{}, inspection, proposal, status, recommendation, failure, message string, exit int) *runnerError {
	payload["status"] = status
	payload["recommendation"] = recommendation
	payload["failure_kind"] = failure
	payload["message"] = message
	return writePayload(payload, inspection, proposal, exit)
}

func writePayload(payload map[string]interface{}, inspection, proposal string, exit int) *runnerError {
	encoded, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return &runnerError{message: err.Error(), exit: 2}
	}
	if err := writeAtomic(inspection, append(encoded, '\n')); err != nil {
		return &runnerError{message: err.Error(), exit: 2}
	}
	if err := writeAtomic(proposal, []byte(renderProposal(payload))); err != nil {
		return &runnerError{message: err.Error(), exit: 2}
	}
	fmt.Printf("wrote %s and %s (%v)\n", inspection, proposal, payload["recommendation"])
	if exit != 0 {
		return &runnerError{message: fmt.Sprintf("proposal stopped: %v", payload["failure_kind"]), exit: exit}
	}
	return nil
}

func inspectTarget(root, parentPath, parent, prefix string, target *packageInfo) ([]moveFile, []moveFile, map[string]bool, []parsedSource, error) {
	active := append([]string{}, target.GoFiles...)
	active = append(active, target.CgoFiles...)
	testNames := append([]string{}, target.TestGoFiles...)
	selected := map[string]bool{}
	cluster := []moveFile{}
	tests := []moveFile{}
	packageAfter := prefixPackage(prefix)
	for _, name := range active {
		path := filepath.Join(parentPath, name)
		contents, err := os.ReadFile(path)
		if err != nil {
			return nil, nil, nil, nil, err
		}
		if generated(contents) || !matchesPrefix(name, prefix) || strings.HasSuffix(name, "_test.go") {
			continue
		}
		current := filepath.ToSlash(filepath.Join(parent, name))
		selected[clean(path)] = true
		cluster = append(cluster, moveFile{CurrentPath: current, NewPath: destination(parent, prefix, name), PackageBefore: target.Name, PackageAfter: packageAfter})
	}
	for _, name := range testNames {
		if !matchesPrefix(name, prefix) {
			continue
		}
		path := filepath.Join(parentPath, name)
		selected[clean(path)] = true
		tests = append(tests, moveFile{CurrentPath: filepath.ToSlash(filepath.Join(parent, name)), NewPath: destination(parent, prefix, name), PackageBefore: target.Name, PackageAfter: packageAfter})
	}
	sort.Slice(cluster, func(i, j int) bool { return cluster[i].CurrentPath < cluster[j].CurrentPath })
	sort.Slice(tests, func(i, j int) bool { return tests[i].CurrentPath < tests[j].CurrentPath })

	allNames := append([]string{}, target.GoFiles...)
	allNames = append(allNames, target.CgoFiles...)
	allNames = append(allNames, target.TestGoFiles...)
	fset := token.NewFileSet()
	parsed := []parsedSource{}
	for _, name := range allNames {
		path := filepath.Join(parentPath, name)
		file, err := parser.ParseFile(fset, path, nil, parser.ParseComments|parser.AllErrors)
		if err != nil {
			return nil, nil, nil, nil, fmt.Errorf("Go syntax error in %s: %w", relative(root, path), err)
		}
		if file.Name.Name != target.Name {
			continue
		}
		parsed = append(parsed, parsedSource{Path: path, AST: file})
	}
	return cluster, tests, selected, parsed, nil
}

func crossBoundaryFacts(root string, target *packageInfo, packages []packageInfo, parsed []parsedSource, selected map[string]bool) ([]crossReference, []string, map[string]declaration, error) {
	fset := token.NewFileSet()
	files := []*ast.File{}
	paths := map[*ast.File]string{}
	for _, source := range parsed {
		file, err := parser.ParseFile(fset, source.Path, nil, parser.ParseComments|parser.AllErrors)
		if err != nil {
			return nil, nil, nil, err
		}
		files = append(files, file)
		paths[file] = source.Path
	}
	var typeErrors []string
	info := &types.Info{Defs: map[*ast.Ident]types.Object{}, Uses: map[*ast.Ident]types.Object{}}
	config := types.Config{Importer: exportImporter(fset, packages), Error: func(err error) { typeErrors = append(typeErrors, err.Error()) }}
	pkg, err := config.Check(target.ImportPath, fset, files, info)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("go/types could not establish target package identity: %s", strings.Join(typeErrors, "; "))
	}
	declarationsByObject := map[types.Object]declaration{}
	declarationsByName := map[string]declaration{}
	for ident, object := range info.Defs {
		if object == nil || pkg == nil || object.Parent() != pkg.Scope() {
			continue
		}
		position := fset.Position(ident.Pos())
		record := declaration{Name: object.Name(), Path: clean(position.Filename), Selected: selected[clean(position.Filename)], Exported: object.Exported()}
		declarationsByObject[object] = record
		declarationsByName[object.Name()] = record
	}
	cross := []crossReference{}
	seen := map[string]bool{}
	for ident, object := range info.Uses {
		declaration, ok := declarationsByObject[object]
		if !ok {
			continue
		}
		position := fset.Position(ident.Pos())
		useSelected := selected[clean(position.Filename)]
		if useSelected == declaration.Selected {
			continue
		}
		direction := "selected_to_parent"
		if !useSelected {
			direction = "parent_to_selected"
		}
		key := fmt.Sprintf("%s:%d:%s:%s", position.Filename, position.Line, object.Name(), direction)
		if seen[key] {
			continue
		}
		seen[key] = true
		cross = append(cross, crossReference{File: relative(root, position.Filename), Line: position.Line, Symbol: object.Name(), DeclaredIn: relative(root, declaration.Path), Exported: declaration.Exported, Direction: direction})
	}
	initRisks := []string{}
	for _, file := range files {
		path := paths[file]
		if !selected[clean(path)] {
			continue
		}
		for _, decl := range file.Decls {
			switch item := decl.(type) {
			case *ast.FuncDecl:
				if item.Recv == nil && item.Name.Name == "init" {
					initRisks = append(initRisks, fmt.Sprintf("%s:%d declares init", relative(root, path), fset.Position(item.Pos()).Line))
				}
			case *ast.GenDecl:
				if item.Tok == token.VAR {
					initRisks = append(initRisks, fmt.Sprintf("%s:%d declares package variable initialization", relative(root, path), fset.Position(item.Pos()).Line))
				}
			}
		}
	}
	sort.Slice(cross, func(i, j int) bool {
		if cross[i].File == cross[j].File {
			return cross[i].Line < cross[j].Line
		}
		return cross[i].File < cross[j].File
	})
	sort.Strings(initRisks)
	return cross, initRisks, declarationsByName, nil
}

func importImpacts(root string, packages []packageInfo, target *packageInfo, declarations map[string]declaration, destinationPath string) ([]importImpact, []string, error) {
	selectedNames := map[string]bool{}
	for _, declaration := range declarations {
		if declaration.Selected && declaration.Exported {
			selectedNames[declaration.Name] = true
		}
	}
	newImport := strings.TrimSuffix(strings.TrimSuffix(target.ImportPath, filepath.ToSlash(filepath.Base(target.Dir))), "/")
	_ = newImport
	modulePrefix := target.ImportPath
	if slash := strings.LastIndex(modulePrefix, "/"); slash >= 0 {
		modulePrefix = modulePrefix[:slash]
	}
	afterImport := strings.TrimSuffix(modulePrefix, "/") + "/" + filepath.Base(destinationPath)
	// destinationPath may be nested; derive by appending the cluster package to the current import path.
	afterImport = strings.TrimSuffix(target.ImportPath, "/") + "/" + filepath.Base(destinationPath)
	impacts := []importImpact{}
	ambiguous := []string{}
	for _, pkg := range packages {
		if clean(pkg.Dir) == clean(target.Dir) || pkg.Dir == "" || pkg.ForTest != "" || strings.HasSuffix(pkg.ImportPath, ".test") {
			continue
		}
		names := append([]string{}, pkg.GoFiles...)
		names = append(names, pkg.CgoFiles...)
		names = append(names, pkg.TestGoFiles...)
		names = append(names, pkg.XTestGoFiles...)
		activeCount := len(names)
		names = append(names, pkg.IgnoredGoFiles...)
		for nameIndex, name := range names {
			path := filepath.Join(pkg.Dir, name)
			set := token.NewFileSet()
			file, err := parser.ParseFile(set, path, nil, parser.AllErrors)
			if err != nil {
				return nil, nil, fmt.Errorf("cannot parse importer %s: %w", relative(root, path), err)
			}
			aliases := []string{}
			for _, spec := range file.Imports {
				value, unquoteErr := strconv.Unquote(spec.Path.Value)
				if unquoteErr != nil || value != target.ImportPath {
					continue
				}
				if nameIndex >= activeCount {
					ambiguous = append(ambiguous, fmt.Sprintf("%s:%d is an inactive importer of the package being split", relative(root, path), set.Position(spec.Pos()).Line))
					continue
				}
				alias := target.Name
				if spec.Name != nil {
					alias = spec.Name.Name
				}
				if alias == "." || alias == "_" {
					ambiguous = append(ambiguous, fmt.Sprintf("%s:%d uses %s import", relative(root, path), set.Position(spec.Pos()).Line, alias))
					continue
				}
				aliases = append(aliases, alias)
			}
			if len(aliases) == 0 {
				continue
			}
			ast.Inspect(file, func(node ast.Node) bool {
				selector, ok := node.(*ast.SelectorExpr)
				if !ok || !selectedNames[selector.Sel.Name] {
					return true
				}
				qualifier, ok := selector.X.(*ast.Ident)
				if !ok || !contains(aliases, qualifier.Name) {
					return true
				}
				position := set.Position(selector.Sel.Pos())
				impacts = append(impacts, importImpact{Importer: relative(root, path), Line: position.Line, CurrentImport: target.ImportPath, AfterImport: afterImport, CurrentQualifier: qualifier.Name, AfterQualifier: prefixPackage(filepath.Base(destinationPath)), Symbol: selector.Sel.Name, Kind: "qualified_reference"})
				return true
			})
		}
	}
	sort.Slice(impacts, func(i, j int) bool {
		if impacts[i].Importer == impacts[j].Importer {
			if impacts[i].Line == impacts[j].Line {
				return impacts[i].Symbol < impacts[j].Symbol
			}
			return impacts[i].Line < impacts[j].Line
		}
		return impacts[i].Importer < impacts[j].Importer
	})
	sort.Strings(ambiguous)
	return impacts, ambiguous, nil
}

func loadConventions(root, supplied, parent, prefix string) (conventionEvidence, error) {
	evidence := conventionEvidence{
		Source:       "none",
		Precedence:   []string{"explicit_project", "detected_framework", "language_safety", "generic_navigation"},
		AppliedRules: []conventionRule{}, DetectedFrameworkRules: []string{},
		LanguageConstraints: []string{"one directory is one Go package", "unexported identifiers do not cross package boundaries", "package initialization semantics must remain explicit"},
		GenericHeuristics:   []string{"three or more prefix siblings suggest a navigational cluster"},
		Conflicts:           []string{}, UnresolvedAssumptions: []string{},
	}
	if supplied == "" {
		return evidence, nil
	}
	path, err := projectPath(root, supplied)
	if err != nil {
		return evidence, err
	}
	contents, err := os.ReadFile(path)
	if err != nil {
		return evidence, err
	}
	var profile conventionProfile
	decoder := json.NewDecoder(bytes.NewReader(contents))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&profile); err != nil {
		return evidence, fmt.Errorf("invalid convention profile: %w", err)
	}
	if profile.SchemaVersion != 1 {
		return evidence, errors.New("convention profile schema_version must be 1")
	}
	evidence.Source = relative(root, path)
	for _, rule := range profile.Rules {
		if filepath.ToSlash(rule.Parent) != filepath.ToSlash(parent) || rule.Prefix != prefix {
			continue
		}
		if rule.Action != "allow_package_split" && rule.Action != "deny_package_split" {
			return evidence, fmt.Errorf("unsupported convention action %q", rule.Action)
		}
		if strings.TrimSpace(rule.Rationale) == "" {
			return evidence, errors.New("matching convention rules require a rationale")
		}
		evidence.AppliedRules = append(evidence.AppliedRules, rule)
	}
	return evidence, nil
}

func conventionActions(rules []conventionRule) (bool, bool) {
	allow, deny := false, false
	for _, rule := range rules {
		allow = allow || rule.Action == "allow_package_split"
		deny = deny || rule.Action == "deny_package_split"
	}
	return allow, deny
}

func moduleFacts(root, goPath string) (moduleInfo, error) {
	output, err := commandOutput(root, goPath, "list", "-m", "-json", "-mod=readonly")
	if err != nil {
		return moduleInfo{}, err
	}
	var module moduleInfo
	if err := json.Unmarshal([]byte(output), &module); err != nil {
		return moduleInfo{}, err
	}
	return module, nil
}

func nestedModules(root string) []string {
	result := []string{}
	_ = filepath.WalkDir(root, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return nil
		}
		if entry.IsDir() {
			if path != root && (entry.Name() == ".git" || entry.Name() == ".agents" || entry.Name() == "vendor" || entry.Name() == "node_modules" || entry.Name() == "reports") {
				return filepath.SkipDir
			}
			return nil
		}
		if entry.Name() == "go.mod" && clean(path) != clean(filepath.Join(root, "go.mod")) {
			result = append(result, relative(root, path))
		}
		return nil
	})
	sort.Strings(result)
	return result
}

func clusterFilesystemRisks(root, parentPath, prefix string) ([]string, error) {
	entries, err := os.ReadDir(parentPath)
	if err != nil {
		return nil, err
	}
	risks := []string{}
	for _, entry := range entries {
		if !matchesPrefix(entry.Name(), prefix) || filepath.Ext(entry.Name()) != ".go" {
			continue
		}
		path := filepath.Join(parentPath, entry.Name())
		info, statErr := os.Lstat(path)
		if statErr != nil {
			return nil, statErr
		}
		if info.Mode()&os.ModeSymlink != 0 {
			risks = append(risks, relative(root, path)+":symlink")
			continue
		}
		contents, readErr := os.ReadFile(path)
		if readErr != nil {
			return nil, readErr
		}
		if generated(contents) {
			risks = append(risks, relative(root, path)+":generated")
		}
	}
	sort.Strings(risks)
	return risks, nil
}

func packageFacts(root, goPath string) ([]packageInfo, error) {
	command := exec.Command(goPath, "list", "-deps", "-test", "-export", "-e", "-json", "-mod=readonly", "./...")
	command.Dir = root
	var stdout, stderr bytes.Buffer
	command.Stdout, command.Stderr = &stdout, &stderr
	if err := command.Run(); err != nil && stdout.Len() == 0 {
		return nil, fmt.Errorf("go list failed: %s", strings.TrimSpace(stderr.String()))
	}
	decoder := json.NewDecoder(bytes.NewReader(stdout.Bytes()))
	packages := []packageInfo{}
	for {
		var item packageInfo
		err := decoder.Decode(&item)
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return nil, err
		}
		packages = append(packages, item)
	}
	if len(packages) == 0 {
		return nil, errors.New("go list returned no package facts")
	}
	return packages, nil
}

func exportImporter(fset *token.FileSet, packages []packageInfo) types.Importer {
	exports := map[string]string{}
	for _, pkg := range packages {
		if pkg.Export != "" {
			exports[pkg.ImportPath] = pkg.Export
		}
	}
	lookup := func(path string) (io.ReadCloser, error) {
		file := exports[path]
		if file == "" {
			return nil, fmt.Errorf("no export data for %s", path)
		}
		return os.Open(file)
	}
	return importer.ForCompiler(fset, "gc", lookup)
}

func renderProposal(payload map[string]interface{}) string {
	status := fmt.Sprint(payload["status"])
	recommendation := fmt.Sprint(payload["recommendation"])
	target, _ := payload["target"].(map[string]interface{})
	lines := []string{
		fmt.Sprintf("# Go folder reorganization proposal — %v::%v", target["parent"], target["prefix"]), "",
		fmt.Sprintf("**Status:** `%s`", status), fmt.Sprintf("**Recommendation:** `%s`", recommendation), "",
		fmt.Sprint(payload["message"]), "", "## Convention basis", "",
		"Precedence: explicit project convention → detected framework convention → language safety → generic navigation heuristic.", "",
	}
	if convention, ok := payload["conventions"].(conventionEvidence); ok {
		lines = append(lines, fmt.Sprintf("- Source: `%s`", convention.Source))
		for _, rule := range convention.AppliedRules {
			lines = append(lines, fmt.Sprintf("- Applied `%s` for `%s::%s`: %s", rule.Action, rule.Parent, rule.Prefix, rule.Rationale))
		}
		for _, conflict := range convention.Conflicts {
			lines = append(lines, fmt.Sprintf("- Conflict: %s", conflict))
		}
		for _, assumption := range convention.UnresolvedAssumptions {
			lines = append(lines, fmt.Sprintf("- Unresolved assumption: %s", assumption))
		}
	}
	lines = append(lines, "", "The >=3 threshold is evidence of a cluster, not authority for a Go package split.", "", "## Move table", "", "| Current | Proposed | Package |", "|---|---|---|")
	if rows, ok := payload["cluster_files"].([]moveFile); ok {
		for _, row := range rows {
			lines = append(lines, fmt.Sprintf("| `%s` | `%s` | `%s` → `%s` |", row.CurrentPath, row.NewPath, row.PackageBefore, row.PackageAfter))
		}
	}
	if rows, ok := payload["test_files"].([]moveFile); ok {
		for _, row := range rows {
			lines = append(lines, fmt.Sprintf("| `%s` | `%s` | `%s` → `%s` |", row.CurrentPath, row.NewPath, row.PackageBefore, row.PackageAfter))
		}
	}
	lines = append(lines, "", "## Complete resolved import-impact table", "", "| Importer | Line | Symbol | Import rewrite |", "|---|---:|---|---|")
	if rows, ok := payload["import_impact"].([]importImpact); ok {
		for _, row := range rows {
			lines = append(lines, fmt.Sprintf("| `%s` | %d | `%s` | `%s` → `%s` |", row.Importer, row.Line, row.Symbol, row.CurrentImport, row.AfterImport))
		}
	}
	if rows, ok := payload["cross_boundary_references"].([]crossReference); ok && len(rows) > 0 {
		lines = append(lines, "", "## Package boundary blockers", "", "Package-private or otherwise cross-boundary references must be redesigned before a move:")
		for _, row := range rows {
			lines = append(lines, fmt.Sprintf("- `%s:%d` uses `%s` declared in `%s` (%s).", row.File, row.Line, row.Symbol, row.DeclaredIn, row.Direction))
		}
	}
	lines = append(lines, "", "## Native characterization and stop conditions", "", "Run before and after the separately reviewed move:", "", "```bash", "go test ./...", "go vet ./...", "```", "", "This proposal makes no source edits. Any move, package declaration change, or import rewrite belongs to the execution skill after human review.", "")
	return strings.Join(lines, "\n")
}

func writeAtomic(path string, contents []byte) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	temporary, err := os.CreateTemp(filepath.Dir(path), ".proposal-*")
	if err != nil {
		return err
	}
	tempName := temporary.Name()
	defer os.Remove(tempName)
	if _, err := temporary.Write(contents); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Sync(); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Close(); err != nil {
		return err
	}
	return os.Rename(tempName, path)
}

func commandOutput(root, executable string, args ...string) (string, error) {
	command := exec.Command(executable, args...)
	command.Dir = root
	var stdout, stderr bytes.Buffer
	command.Stdout, command.Stderr = &stdout, &stderr
	if err := command.Run(); err != nil {
		return "", fmt.Errorf("%s: %s", err, strings.TrimSpace(stderr.String()))
	}
	return stdout.String(), nil
}

func artifactPath(root, supplied string) (string, error) {
	path, err := projectPath(root, supplied)
	if err != nil {
		return "", err
	}
	allowed := filepath.Join(root, "reports", "propose-folder-reorganization")
	if !within(allowed, path) || clean(path) == clean(allowed) {
		return "", errors.New("artifact path must stay beneath reports/propose-folder-reorganization")
	}
	if err := rejectSymlinkPath(root, path); err != nil {
		return "", err
	}
	return path, nil
}

func projectPath(root, supplied string) (string, error) {
	path := supplied
	if !filepath.IsAbs(path) {
		path = filepath.Join(root, path)
	}
	path = filepath.Clean(path)
	if !within(root, path) {
		return "", fmt.Errorf("path must stay inside project root: %s", supplied)
	}
	if err := rejectSymlinkPath(root, path); err != nil {
		return "", err
	}
	return path, nil
}

func rejectSymlinkPath(root, path string) error {
	rel, err := filepath.Rel(root, path)
	if err != nil {
		return err
	}
	current := root
	for _, part := range strings.Split(rel, string(filepath.Separator)) {
		if part == "" || part == "." {
			continue
		}
		current = filepath.Join(current, part)
		info, statErr := os.Lstat(current)
		if os.IsNotExist(statErr) {
			continue
		}
		if statErr != nil {
			return statErr
		}
		if info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("path must not traverse a symbolic link: %s", path)
		}
	}
	return nil
}

func within(root, path string) bool {
	rel, err := filepath.Rel(root, path)
	return err == nil && rel != ".." && !strings.HasPrefix(rel, ".."+string(filepath.Separator)) && !filepath.IsAbs(rel)
}

func internalPackagePath(parent string) bool {
	for _, part := range strings.Split(filepath.ToSlash(parent), "/") {
		if part == "internal" {
			return true
		}
	}
	return false
}

func relative(root, path string) string {
	rel, err := filepath.Rel(root, path)
	if err != nil {
		return filepath.ToSlash(path)
	}
	return filepath.ToSlash(rel)
}

func clean(path string) string { absolute, _ := filepath.Abs(path); return filepath.Clean(absolute) }

func matchesPrefix(name, prefix string) bool {
	stem := strings.TrimSuffix(name, filepath.Ext(name))
	return strings.HasPrefix(stem, prefix+"_") || strings.HasPrefix(stem, prefix+"-")
}

func matchingNames(names []string, prefix string) []string {
	result := []string{}
	for _, name := range names {
		if matchesPrefix(name, prefix) {
			result = append(result, name)
		}
	}
	sort.Strings(result)
	return result
}

func destination(parent, prefix, name string) string {
	stem := strings.TrimSuffix(name, ".go")
	suffix := strings.TrimPrefix(strings.TrimPrefix(stem, prefix+"_"), prefix+"-")
	return filepath.ToSlash(filepath.Join(parent, prefix, suffix+".go"))
}

func prefixPackage(prefix string) string {
	var builder strings.Builder
	for _, char := range prefix {
		if unicode.IsLetter(char) || unicode.IsDigit(char) || char == '_' {
			builder.WriteRune(char)
		}
	}
	return builder.String()
}

func validPrefix(prefix string) bool {
	if prefix == "" {
		return false
	}
	for index, char := range prefix {
		if !(unicode.IsLetter(char) || unicode.IsDigit(char) || char == '_' || char == '-') || (index == 0 && !unicode.IsLetter(char)) {
			return false
		}
	}
	return true
}

func generated(contents []byte) bool {
	for _, line := range strings.Split(string(contents), "\n") {
		if strings.HasPrefix(strings.TrimSpace(line), "// Code generated ") && strings.Contains(line, "DO NOT EDIT.") {
			return true
		}
	}
	return false
}

func contains(values []string, value string) bool {
	for _, item := range values {
		if item == value {
			return true
		}
	}
	return false
}

func atLeastGoVersion(actual, minimum string) bool {
	parse := func(value string) (int, int) {
		value = strings.TrimPrefix(value, "go")
		parts := strings.Split(value, ".")
		major, minor := 0, 0
		if len(parts) > 0 {
			major, _ = strconv.Atoi(numericPrefix(parts[0]))
		}
		if len(parts) > 1 {
			minor, _ = strconv.Atoi(numericPrefix(parts[1]))
		}
		return major, minor
	}
	actualMajor, actualMinor := parse(actual)
	minimumMajor, minimumMinor := parse(minimum)
	return actualMajor > minimumMajor || (actualMajor == minimumMajor && actualMinor >= minimumMinor)
}

func numericPrefix(value string) string {
	end := 0
	for end < len(value) && value[end] >= '0' && value[end] <= '9' {
		end++
	}
	return value[:end]
}
