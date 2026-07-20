// Produce a conservative, read-only Go boundary proposal from module/package facts.
//
// This command intentionally uses only the Go toolchain and the standard
// library. go list establishes the active module/package graph; go/parser and
// go/ast establish declarations, imports, and syntax-level local calls. It
// does not claim go/types-level call identity, build-tag completeness, runtime
// reachability, or framework semantics.
package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
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
	Path      string      `json:"Path"`
	Dir       string      `json:"Dir"`
	GoVersion string      `json:"GoVersion"`
	Replace   *moduleInfo `json:"Replace"`
}

type packageError struct {
	Err string `json:"Err"`
}

type packageInfo struct {
	Dir            string        `json:"Dir"`
	ImportPath     string        `json:"ImportPath"`
	Name           string        `json:"Name"`
	GoFiles        []string      `json:"GoFiles"`
	CgoFiles       []string      `json:"CgoFiles"`
	IgnoredGoFiles []string      `json:"IgnoredGoFiles"`
	TestGoFiles    []string      `json:"TestGoFiles"`
	Imports        []string      `json:"Imports"`
	Error          *packageError `json:"Error"`
	Incomplete     bool          `json:"Incomplete"`
}

type symbol struct {
	Name      string `json:"name"`
	File      string `json:"file"`
	Line      int    `json:"line"`
	Kind      string `json:"kind"`
	Exported  bool   `json:"exported"`
	Domain    string `json:"domain"`
	Signature string `json:"signature"`
}

type callEdge struct {
	Caller     string `json:"caller_symbol"`
	Callee     string `json:"callee_symbol"`
	File       string `json:"file"`
	Line       int    `json:"line"`
	Resolution string `json:"resolution"`
}

type importImpact struct {
	CallerPackage string `json:"caller_package"`
	CallerDir     string `json:"caller_dir"`
	File          string `json:"file"`
	Line          int    `json:"line"`
	ImportPath    string `json:"import_path"`
	LocalName     string `json:"local_name"`
	Style         string `json:"style"`
}

type candidateSeam struct {
	ClusterID                 string     `json:"cluster_id"`
	Members                   []string   `json:"members"`
	ProposedPublicAPI         []string   `json:"proposed_public_api"`
	PrivateCrossDomainCalls   []callEdge `json:"private_cross_domain_calls"`
	Rationale                 string     `json:"rationale"`
	Scores                    any        `json:"scores"`
	SyntaxOnlyLocalCallNotice string     `json:"syntax_only_local_call_notice"`
}

type candidateSelection struct {
	Requested    int     `json:"requested"`
	Eligible     int     `json:"eligible"`
	Returned     int     `json:"returned"`
	CutoffScore  float64 `json:"cutoff_score"`
	TiesIncluded bool    `json:"ties_included"`
	OmittedCount int     `json:"omitted_count"`
	Omitted      []any   `json:"omitted"`
}

type runnerError struct {
	message string
	status  string
	reason  string
	exit    int
}

func (err *runnerError) Error() string { return err.message }

func main() {
	var target, projectRoot, inspection, proposal, minimumGo string
	var candidates int
	flag.StringVar(&target, "target", "", "Go package directory or .go file within the project root")
	flag.StringVar(&projectRoot, "project-root", ".", "host project root")
	flag.StringVar(&inspection, "inspection", "", "reports/propose-boundary/<name>/inspection.json")
	flag.StringVar(&proposal, "proposal", "", "reports/propose-boundary/<name>/proposal.md")
	flag.StringVar(&minimumGo, "minimum-go", defaultMinimumGo, "minimum required Go version")
	flag.IntVar(&candidates, "candidates", 1, "number of top candidate seams, including cutoff ties")
	flag.Parse()

	if target == "" || inspection == "" || proposal == "" || candidates < 1 {
		fmt.Fprintln(os.Stderr, "usage: propose_go.go --target <path> --project-root <path> --inspection <path> --proposal <path> [--candidates N]")
		os.Exit(2)
	}
	root, err := filepath.Abs(projectRoot)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	if err := rejectSymlinkPath(root, root); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
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

	if runErr := run(target, root, inspectionPath, proposalPath, candidates, minimumGo); runErr != nil {
		fmt.Fprintf(os.Stderr, "[propose_go] %s\n", runErr.message)
		if runErr.exit != 0 {
			os.Exit(runErr.exit)
		}
	}
}

func run(target, root, inspectionPath, proposalPath string, requested int, minimumGo string) *runnerError {
	goPath, err := exec.LookPath("go")
	if err != nil {
		return writeTerminal(root, inspectionPath, proposalPath, target, "unsupported", "defer_tool_missing", "go_tool_missing", "Go was not found on PATH.", 0)
	}
	versionText, err := commandOutput(root, goPath, "version")
	if err != nil {
		return writeTerminal(root, inspectionPath, proposalPath, target, "unsupported", "defer_tool_unavailable", "go_version_failed", err.Error(), 0)
	}
	version := strings.TrimSpace(strings.TrimPrefix(versionText, "go version "))
	if !atLeastGoVersion(version, minimumGo) {
		return writeTerminal(root, inspectionPath, proposalPath, target, "unsupported", "defer_go_version", "go_version_too_old", fmt.Sprintf("Go %s is below the required Go %s.", version, minimumGo), 0)
	}

	targetPath, err := projectPath(root, target)
	if err != nil {
		return writeTerminal(root, inspectionPath, proposalPath, target, "unsupported", "defer_unsafe_target", "unsafe_target", err.Error(), 0)
	}
	if err := rejectSymlinkPath(root, targetPath); err != nil {
		return writeTerminal(root, inspectionPath, proposalPath, target, "unsupported", "defer_unsafe_target", "unsafe_target", err.Error(), 0)
	}
	info, err := os.Stat(targetPath)
	if err != nil {
		return writeTerminal(root, inspectionPath, proposalPath, target, "unsupported", "defer_target_not_found", "target_not_found", err.Error(), 0)
	}
	targetDir := targetPath
	if !info.IsDir() {
		if filepath.Ext(targetPath) != ".go" {
			return writeTerminal(root, inspectionPath, proposalPath, target, "unsupported", "defer_target_unsupported", "target_not_go_source", "Target must be a Go package directory or .go file.", 0)
		}
		targetDir = filepath.Dir(targetPath)
	}
	if excludedPath(root, targetPath) {
		return writeTerminal(root, inspectionPath, proposalPath, target, "unsupported", "defer_excluded_target", "excluded_target", "Generated, vendor, and test targets are outside the Go proposal v1 scope.", 0)
	}

	module, moduleErr := moduleFacts(root, goPath)
	if moduleErr != nil || module.Path == "" || module.Dir == "" {
		message := "A single Go module rooted at the project is required."
		if moduleErr != nil {
			message = moduleErr.Error()
		}
		return writeTerminal(root, inspectionPath, proposalPath, target, "unsupported", "defer_not_go_module", "go_module_required", message, 0)
	}
	if clean(module.Dir) != clean(root) || module.Replace != nil {
		return writeTerminal(root, inspectionPath, proposalPath, target, "unsupported", "defer_module_topology", "module_replace_or_nonroot", "Go proposal v1 requires the project root module without a replacement.", 0)
	}

	files, excluded, parseErr := targetSourceFiles(root, targetPath, targetDir)
	if parseErr != nil {
		return writeTerminal(root, inspectionPath, proposalPath, target, "failed", "defer_syntax_error", "syntax_error", parseErr.Error(), 2)
	}
	if len(files) == 0 {
		return writeTerminal(root, inspectionPath, proposalPath, target, "unsupported", "defer_excluded_target", "no_eligible_go_source", "Target contains no eligible production Go files.", 0)
	}

	packages, listErr := packageFacts(root, goPath)
	if listErr != nil {
		return writeTerminal(root, inspectionPath, proposalPath, target, "partial", "defer_unresolved_package_graph", "go_list_failed", listErr.Error(), 0)
	}
	var selected *packageInfo
	for index := range packages {
		if clean(packages[index].Dir) == clean(targetDir) {
			selected = &packages[index]
			break
		}
	}
	if selected == nil || selected.Error != nil || selected.Incomplete || selected.ImportPath == "" {
		return writeTerminal(root, inspectionPath, proposalPath, target, "partial", "defer_unresolved_package_graph", "unresolved_target_package", "go list could not establish a complete target package.", 0)
	}
	if len(selected.IgnoredGoFiles) > 0 || len(selected.CgoFiles) > 0 {
		return writeTerminal(root, inspectionPath, proposalPath, target, "partial", "defer_build_constraints", "ignored_or_cgo_files", "Build-tagged or cgo source makes the selected package configuration-dependent.", 0)
	}

	symbols, calls, packageName, parseErr := inspectFiles(root, files)
	if parseErr != nil {
		return writeTerminal(root, inspectionPath, proposalPath, target, "failed", "defer_syntax_error", "syntax_error", parseErr.Error(), 2)
	}
	if packageName != selected.Name {
		return writeTerminal(root, inspectionPath, proposalPath, target, "partial", "defer_ambiguous_package", "package_name_mismatch", "Parsed package declarations do not match go list package facts.", 0)
	}
	impacts, ambiguous, callerErr := callerImpacts(root, packages, selected.ImportPath, selected.Name)
	if callerErr != nil {
		return writeTerminal(root, inspectionPath, proposalPath, target, "partial", "defer_unresolved_caller_graph", "caller_parse_error", callerErr.Error(), 0)
	}
	if len(ambiguous) > 0 {
		payload := basePayload(root, targetPath, files, excluded, goPath, version, minimumGo, module, selected, symbols, calls, impacts)
		payload["status"] = "partial"
		payload["recommendation"] = "defer_ambiguous_caller_evidence"
		payload["defer_signals"] = []string{"ambiguous_import_form"}
		payload["ambiguous_caller_evidence"] = ambiguous
		return writePayload(inspectAndProposal{inspectionPath, proposalPath, payload}, 0)
	}

	ranked := candidateSeams(symbols, calls)
	seams, selection := selectSeams(ranked, requested)
	payload := basePayload(root, targetPath, files, excluded, goPath, version, minimumGo, module, selected, symbols, calls, impacts)
	payload["candidate_seams"] = seams
	payload["candidate_selection"] = selection
	payload["defer_signals"] = []string{}
	if len(seams) == 0 {
		payload["status"] = "complete"
		payload["recommendation"] = "defer_no_seam"
		payload["defer_signals"] = []string{"single_cluster_no_seam"}
	} else {
		payload["status"] = "complete"
		payload["recommendation"] = "refactor"
	}
	return writePayload(inspectAndProposal{inspectionPath, proposalPath, payload}, 0)
}

type inspectAndProposal struct {
	inspection string
	proposal   string
	payload    map[string]any
}

func writeTerminal(root, inspection, proposal, target, status, recommendation, reason, message string, exit int) *runnerError {
	payload := map[string]any{
		"schema_version":      1,
		"skill":               "propose-boundary",
		"language":            "go",
		"analyzer":            "go-list-plus-stdlib-ast",
		"status":              status,
		"recommendation":      recommendation,
		"target":              map[string]any{"path": target},
		"failure_kind":        reason,
		"message":             message,
		"candidate_seams":     []any{},
		"candidate_selection": candidateSelection{Requested: 0, Eligible: 0, Returned: 0, Omitted: []any{}},
		"defer_signals":       []string{reason},
	}
	if err := writePayload(inspectAndProposal{inspection, proposal, payload}, exit); err != nil {
		return err
	}
	return &runnerError{message: message, status: status, reason: reason, exit: exit}
}

func writePayload(result inspectAndProposal, exit int) *runnerError {
	encoded, err := json.MarshalIndent(result.payload, "", "  ")
	if err != nil {
		return &runnerError{message: err.Error(), exit: 2}
	}
	if err := writeAtomic(result.inspection, append(encoded, '\n')); err != nil {
		return &runnerError{message: err.Error(), exit: 2}
	}
	if err := writeAtomic(result.proposal, []byte(renderProposal(result.payload))); err != nil {
		return &runnerError{message: err.Error(), exit: 2}
	}
	fmt.Printf("wrote %s and %s (%s)\n", result.inspection, result.proposal, result.payload["recommendation"])
	if exit != 0 {
		return &runnerError{message: fmt.Sprintf("proposal stopped: %s", result.payload["failure_kind"]), exit: exit}
	}
	return nil
}

func basePayload(root, targetPath string, files, excluded []string, goPath, version, minimum string, module moduleInfo, selected *packageInfo, symbols []symbol, calls []callEdge, impacts []importImpact) map[string]any {
	return map[string]any{
		"schema_version": 1,
		"skill":          "propose-boundary",
		"language":       "go",
		"analyzer":       "go-list-plus-stdlib-ast",
		"tooling": map[string]any{
			"go_path": goPath, "go_version": version, "minimum_go": minimum,
			"parser": "go/parser and go/ast (standard library)",
		},
		"module": map[string]any{"path": module.Path, "go_version": module.GoVersion},
		"target": map[string]any{
			"path": relative(root, targetPath), "kind": "package_directory", "source_files": len(files), "excluded_files": excluded,
			"package": selected.Name, "import_path": selected.ImportPath,
		},
		"symbols": symbols,
		"graph": map[string]any{
			"package_resolution": "complete", "inbound_imports": impacts, "syntax_local_calls": calls,
			"call_identity_limit": "Local calls are syntax candidates only; this v1 does not claim go/types call identity.",
		},
		"caller_impact": impacts,
		"native_verification": map[string]any{
			"commands": []string{"gofmt -w <human-approved changed .go files>", "go test ./..."},
			"scope":    "This read-only proposal does not run gofmt because gofmt mutates source.",
		},
	}
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

func packageFacts(root, goPath string) ([]packageInfo, error) {
	command := exec.Command(goPath, "list", "-e", "-json", "-mod=readonly", "./...")
	command.Dir = root
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	command.Stdout = &stdout
	command.Stderr = &stderr
	err := command.Run()
	if err != nil {
		return nil, fmt.Errorf("go list failed: %s", strings.TrimSpace(stderr.String()))
	}
	decoder := json.NewDecoder(bytes.NewReader(stdout.Bytes()))
	var packages []packageInfo
	for {
		var item packageInfo
		decodeErr := decoder.Decode(&item)
		if errors.Is(decodeErr, io.EOF) {
			break
		}
		if decodeErr != nil {
			return nil, decodeErr
		}
		packages = append(packages, item)
	}
	if len(packages) == 0 {
		return nil, errors.New("go list returned no package facts")
	}
	return packages, nil
}

func targetSourceFiles(root, targetPath, targetDir string) ([]string, []string, error) {
	entries, err := os.ReadDir(targetDir)
	if err != nil {
		return nil, nil, err
	}
	files, excluded := []string{}, []string{}
	for _, entry := range entries {
		if entry.IsDir() || entry.Type()&os.ModeSymlink != 0 || filepath.Ext(entry.Name()) != ".go" {
			continue
		}
		path := filepath.Join(targetDir, entry.Name())
		if !isWithin(targetPath, path) && filepath.Clean(targetPath) != filepath.Clean(targetDir) {
			continue
		}
		if strings.HasSuffix(entry.Name(), "_test.go") {
			excluded = append(excluded, relative(root, path)+":test")
			continue
		}
		contents, readErr := os.ReadFile(path)
		if readErr != nil {
			return nil, nil, readErr
		}
		if generated(contents) {
			excluded = append(excluded, relative(root, path)+":generated")
			continue
		}
		if _, parseErr := parser.ParseFile(token.NewFileSet(), path, contents, parser.AllErrors); parseErr != nil {
			return nil, nil, fmt.Errorf("Go syntax error in %s: %w", relative(root, path), parseErr)
		}
		files = append(files, path)
	}
	sort.Strings(files)
	sort.Strings(excluded)
	return files, excluded, nil
}

func inspectFiles(root string, files []string) ([]symbol, []callEdge, string, error) {
	fset := token.NewFileSet()
	var packageName string
	var records []symbol
	filesByAST := map[*ast.File]string{}
	for _, path := range files {
		file, err := parser.ParseFile(fset, path, nil, parser.AllErrors)
		if err != nil {
			return nil, nil, "", fmt.Errorf("Go syntax error in %s: %w", relative(root, path), err)
		}
		if packageName == "" {
			packageName = file.Name.Name
		} else if packageName != file.Name.Name {
			return nil, nil, "", fmt.Errorf("multiple package names: %s and %s", packageName, file.Name.Name)
		}
		filesByAST[file] = path
		for _, declaration := range file.Decls {
			switch item := declaration.(type) {
			case *ast.FuncDecl:
				if item.Name != nil {
					records = append(records, makeSymbol(root, fset, path, item.Name, "function"))
				}
			case *ast.GenDecl:
				for _, spec := range item.Specs {
					switch typed := spec.(type) {
					case *ast.TypeSpec:
						records = append(records, makeSymbol(root, fset, path, typed.Name, "type"))
					case *ast.ValueSpec:
						kind := "variable"
						if item.Tok == token.CONST {
							kind = "constant"
						}
						for _, name := range typed.Names {
							records = append(records, makeSymbol(root, fset, path, name, kind))
						}
					}
				}
			}
		}
	}
	byName := map[string]symbol{}
	for _, record := range records {
		byName[record.Name] = record
	}
	var calls []callEdge
	for file, path := range filesByAST {
		for _, declaration := range file.Decls {
			function, ok := declaration.(*ast.FuncDecl)
			if !ok || function.Body == nil || function.Name == nil {
				continue
			}
			ast.Inspect(function.Body, func(node ast.Node) bool {
				call, ok := node.(*ast.CallExpr)
				if !ok {
					return true
				}
				callee, ok := call.Fun.(*ast.Ident)
				if !ok {
					return true
				}
				if _, exists := byName[callee.Name]; !exists {
					return true
				}
				position := fset.Position(call.Pos())
				calls = append(calls, callEdge{Caller: function.Name.Name, Callee: callee.Name, File: relative(root, path), Line: position.Line, Resolution: "syntax_candidate"})
				return true
			})
		}
	}
	sort.Slice(records, func(i, j int) bool {
		return records[i].Name < records[j].Name || (records[i].Name == records[j].Name && records[i].File < records[j].File)
	})
	sort.Slice(calls, func(i, j int) bool {
		return calls[i].Caller < calls[j].Caller || (calls[i].Caller == calls[j].Caller && calls[i].Callee < calls[j].Callee)
	})
	return records, calls, packageName, nil
}

func makeSymbol(root string, fset *token.FileSet, path string, identifier *ast.Ident, kind string) symbol {
	position := fset.Position(identifier.Pos())
	return symbol{Name: identifier.Name, File: relative(root, path), Line: position.Line, Kind: kind, Exported: token.IsExported(identifier.Name), Domain: leadingDomain(identifier.Name), Signature: kind + " " + identifier.Name}
}

func callerImpacts(root string, packages []packageInfo, targetImportPath, targetPackageName string) ([]importImpact, []string, error) {
	var impacts []importImpact
	var ambiguous []string
	for _, item := range packages {
		if item.ImportPath == targetImportPath || !contains(item.Imports, targetImportPath) {
			continue
		}
		if item.Error != nil || item.Incomplete {
			return nil, nil, fmt.Errorf("caller package %s is incomplete", item.ImportPath)
		}
		for _, name := range item.GoFiles {
			path := filepath.Join(item.Dir, name)
			fset := token.NewFileSet()
			file, err := parser.ParseFile(fset, path, nil, parser.ImportsOnly)
			if err != nil {
				return nil, nil, err
			}
			for _, spec := range file.Imports {
				importPath, _ := strconv.Unquote(spec.Path.Value)
				if importPath != targetImportPath {
					continue
				}
				localName, style := targetPackageName, "default"
				if spec.Name != nil {
					localName = spec.Name.Name
					switch localName {
					case ".", "_":
						ambiguous = append(ambiguous, fmt.Sprintf("%s imports %s with %q", relative(root, path), importPath, localName))
						continue
					default:
						style = "alias"
					}
				}
				position := fset.Position(spec.Pos())
				impacts = append(impacts, importImpact{CallerPackage: item.ImportPath, CallerDir: relative(root, item.Dir), File: relative(root, path), Line: position.Line, ImportPath: importPath, LocalName: localName, Style: style})
			}
		}
	}
	sort.Slice(impacts, func(i, j int) bool {
		return impacts[i].File < impacts[j].File || (impacts[i].File == impacts[j].File && impacts[i].LocalName < impacts[j].LocalName)
	})
	sort.Strings(ambiguous)
	return impacts, ambiguous, nil
}

func candidateSeams(symbols []symbol, calls []callEdge) []candidateSeam {
	byDomain := map[string][]symbol{}
	byName := map[string]symbol{}
	for _, item := range symbols {
		byName[item.Name] = item
		if len(item.Domain) >= 3 {
			byDomain[item.Domain] = append(byDomain[item.Domain], item)
		}
	}
	var viable []string
	for domain, members := range byDomain {
		if len(members) >= 2 {
			viable = append(viable, domain)
		}
	}
	if len(viable) < 2 {
		return nil
	}
	sort.Strings(viable)
	var seams []candidateSeam
	for _, domain := range viable {
		members := byDomain[domain]
		memberNames := map[string]bool{}
		var names, exported []string
		for _, member := range members {
			memberNames[member.Name] = true
			names = append(names, member.Name)
			if member.Exported {
				exported = append(exported, member.Name)
			}
		}
		sort.Strings(names)
		sort.Strings(exported)
		var privateCalls []callEdge
		for _, edge := range calls {
			callee, exists := byName[edge.Callee]
			if !exists || !memberNames[edge.Callee] || callee.Exported {
				continue
			}
			caller := byName[edge.Caller]
			if caller.Domain != domain {
				privateCalls = append(privateCalls, edge)
			}
		}
		score := float64(len(members))
		seams = append(seams, candidateSeam{
			ClusterID: domain, Members: names, ProposedPublicAPI: exported, PrivateCrossDomainCalls: privateCalls,
			Rationale:                 fmt.Sprintf("%d top-level declarations share the %s domain token in one Go package.", len(members), domain),
			Scores:                    map[string]float64{"named_member_count": score, "combined": score},
			SyntaxOnlyLocalCallNotice: "Private cross-domain calls are AST syntax candidates, not go/types-resolved call identities.",
		})
	}
	sort.Slice(seams, func(i, j int) bool {
		left := seams[i].Scores.(map[string]float64)["combined"]
		right := seams[j].Scores.(map[string]float64)["combined"]
		return left > right || (left == right && seams[i].ClusterID < seams[j].ClusterID)
	})
	return seams
}

func selectSeams(ranked []candidateSeam, requested int) ([]candidateSeam, candidateSelection) {
	if len(ranked) == 0 {
		return []candidateSeam{}, candidateSelection{Requested: requested, Omitted: []any{}}
	}
	cutoffIndex := requested - 1
	if cutoffIndex >= len(ranked) {
		cutoffIndex = len(ranked) - 1
	}
	cutoff := ranked[cutoffIndex].Scores.(map[string]float64)["combined"]
	selected := []candidateSeam{}
	omitted := []any{}
	for _, seam := range ranked {
		if seam.Scores.(map[string]float64)["combined"] >= cutoff {
			selected = append(selected, seam)
		} else {
			omitted = append(omitted, map[string]any{"cluster_id": seam.ClusterID, "score": seam.Scores.(map[string]float64)["combined"]})
		}
	}
	return selected, candidateSelection{Requested: requested, Eligible: len(ranked), Returned: len(selected), CutoffScore: cutoff, TiesIncluded: len(selected) > requested, OmittedCount: len(omitted), Omitted: omitted}
}

func renderProposal(payload map[string]any) string {
	status, _ := payload["status"].(string)
	recommendation, _ := payload["recommendation"].(string)
	target, _ := payload["target"].(map[string]any)
	path, _ := target["path"].(string)
	var lines []string
	lines = append(lines, "# Boundary proposal — "+path, "", "> **Detected by:** `/propose-boundary` Go v1 (read-only; no edits applied)", "> **Executed by:** `/refactor-subsystem` only after human approval.", "", "Recommendation: **"+recommendation+"**", "")
	if tooling, ok := payload["tooling"].(map[string]any); ok {
		lines = append(lines, "## Native Go evidence", "", fmt.Sprintf("- Go: `%v` (`%v`; minimum `%v`).", tooling["go_path"], tooling["go_version"], tooling["minimum_go"]), "- Package/import resolution: `go list -e -json -mod=readonly ./...`.", "- Source facts: standard-library `go/parser` and `go/ast`; no `go/packages` dependency.", "")
	}
	if status != "complete" || recommendation != "refactor" {
		lines = append(lines, "## Stop condition", "", fmt.Sprintf("No extraction proposal is safe: %v.", payload["message"]), "Resolve the reported package, caller, build, or tool constraint and rerun this read-only proposal.", "")
		return strings.Join(lines, "\n") + "\n"
	}
	selection := payload["candidate_selection"].(candidateSelection)
	lines = append(lines, "## Candidate selection", "", fmt.Sprintf("Requested %d; returned %d of %d eligible; cutoff %.0f; ties included: %t; omitted %d.", selection.Requested, selection.Returned, selection.Eligible, selection.CutoffScore, selection.TiesIncluded, selection.OmittedCount), "")
	seams := payload["candidate_seams"].([]candidateSeam)
	for index, seam := range seams {
		lines = append(lines, fmt.Sprintf("## Candidate seam %d — %s (score: %.0f)", index+1, seam.ClusterID, seam.Scores.(map[string]float64)["combined"]), "", "**Members.** `"+strings.Join(seam.Members, "`, `")+"`.", "", "**Proposed public API.**", "", "| Symbol | Current role |", "|---|---|")
		if len(seam.ProposedPublicAPI) == 0 {
			lines = append(lines, "| _None_ | A human must choose an exported contract before extraction. |")
		}
		for _, name := range seam.ProposedPublicAPI {
			lines = append(lines, "| `"+name+"` | Preserve this exported package API through the temporary compatibility facade. |")
		}
		lines = append(lines, "", "**Private cross-domain calls.**", "")
		if len(seam.PrivateCrossDomainCalls) == 0 {
			lines = append(lines, "None found in syntax-only local-call evidence.")
		} else {
			for _, edge := range seam.PrivateCrossDomainCalls {
				lines = append(lines, fmt.Sprintf("- `%s` calls package-private `%s` at `%s:%d`; define an explicit exported or injected boundary before splitting packages.", edge.Caller, edge.Callee, edge.File, edge.Line))
			}
			lines = append(lines, "- "+seam.SyntaxOnlyLocalCallNotice)
		}
		lines = append(lines, "")
	}
	lines = append(lines, "## Caller impact", "", "| Caller package | File | Import path | Local name | Style |", "|---|---|---|---|---|")
	impacts := payload["caller_impact"].([]importImpact)
	if len(impacts) == 0 {
		lines = append(lines, "| _None_ | _None_ | _None_ | _None_ | _None_ |")
	}
	for _, impact := range impacts {
		lines = append(lines, fmt.Sprintf("| `%s` | `%s` | `%s` | `%s` | %s |", impact.CallerPackage, impact.File, impact.ImportPath, impact.LocalName, impact.Style))
	}
	lines = append(lines, "", "## Compatibility and verification plan", "", "1. Keep the existing package import path as a temporary facade; use forwarding functions and type aliases only for the human-approved exported API.", "2. Do not expose package-private helpers merely to make a split compile; migrate their callers to an explicit boundary.", "3. Add characterization tests for each exported API and each listed direct or alias importer.", "4. After the human-approved refactor, run:", "   - `gofmt -w <human-approved changed .go files>`", "   - `go test ./...`", "", "## Stop condition", "", "Every listed importer uses the approved public boundary, package-private cross-domain reaches are removed or deliberately retained, and the native checks remain green.", "")
	return strings.Join(lines, "\n") + "\n"
}

func commandOutput(dir, program string, args ...string) (string, error) {
	command := exec.Command(program, args...)
	command.Dir = dir
	output, err := command.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("%s %s failed: %s", program, strings.Join(args, " "), strings.TrimSpace(string(output)))
	}
	return string(output), nil
}

func atLeastGoVersion(raw, minimum string) bool {
	major, minor, ok := goVersionParts(raw)
	if !ok {
		return false
	}
	minMajor, minMinor, ok := goVersionParts("go" + minimum)
	return ok && (major > minMajor || (major == minMajor && minor >= minMinor))
}

func goVersionParts(raw string) (int, int, bool) {
	trimmed := strings.TrimPrefix(strings.TrimSpace(raw), "go")
	parts := strings.Split(trimmed, ".")
	if len(parts) < 2 {
		return 0, 0, false
	}
	major, firstErr := strconv.Atoi(parts[0])
	minor, secondErr := strconv.Atoi(parts[1])
	return major, minor, firstErr == nil && secondErr == nil
}

func projectPath(root, supplied string) (string, error) {
	candidate := supplied
	if !filepath.IsAbs(candidate) {
		candidate = filepath.Join(root, candidate)
	}
	candidate, err := filepath.Abs(candidate)
	if err != nil {
		return "", err
	}
	if !isWithin(root, candidate) {
		return "", fmt.Errorf("path must stay inside project root: %s", supplied)
	}
	return candidate, nil
}

func artifactPath(root, supplied string) (string, error) {
	candidate, err := projectPath(root, supplied)
	if err != nil {
		return "", err
	}
	reportRoot := filepath.Join(root, "reports", "propose-boundary")
	if !isWithin(reportRoot, candidate) || clean(candidate) == clean(reportRoot) {
		return "", fmt.Errorf("artifact must stay below reports/propose-boundary: %s", supplied)
	}
	if err := rejectSymlinkPath(root, candidate); err != nil {
		return "", err
	}
	return candidate, nil
}

func rejectSymlinkPath(root, candidate string) error {
	if !isWithin(root, candidate) {
		return errors.New("path escapes project root")
	}
	parts, err := filepath.Rel(root, candidate)
	if err != nil {
		return err
	}
	current := root
	if info, err := os.Lstat(current); err == nil && info.Mode()&os.ModeSymlink != 0 {
		return errors.New("project root must not be a symbolic link")
	}
	for _, part := range strings.Split(parts, string(os.PathSeparator)) {
		if part == "." || part == "" {
			continue
		}
		current = filepath.Join(current, part)
		info, err := os.Lstat(current)
		if os.IsNotExist(err) {
			break
		}
		if err != nil {
			return err
		}
		if info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("path must not traverse a symbolic link: %s", candidate)
		}
	}
	return nil
}

func excludedPath(root, path string) bool {
	rel := relative(root, path)
	for _, part := range strings.Split(rel, "/") {
		switch strings.ToLower(part) {
		case "vendor", "generated", "gen", "test", "tests", "fixtures", "fixture":
			return true
		}
	}
	return strings.HasSuffix(strings.ToLower(path), "_test.go")
}

func generated(contents []byte) bool {
	lines := strings.Split(string(contents), "\n")
	limit := len(lines)
	if limit > 5 {
		limit = 5
	}
	for _, line := range lines[:limit] {
		if strings.Contains(line, "Code generated") && strings.Contains(line, "DO NOT EDIT") {
			return true
		}
	}
	return false
}

func writeAtomic(path string, contents []byte) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	temporary := path + ".tmp-" + strconv.Itoa(os.Getpid())
	if err := os.WriteFile(temporary, contents, 0o644); err != nil {
		return err
	}
	return os.Rename(temporary, path)
}

func clean(path string) string { return filepath.Clean(path) }

func relative(root, path string) string {
	rel, err := filepath.Rel(root, path)
	if err != nil {
		return path
	}
	return filepath.ToSlash(rel)
}

func isWithin(root, candidate string) bool {
	rel, err := filepath.Rel(root, candidate)
	return err == nil && rel != ".." && !strings.HasPrefix(rel, ".."+string(os.PathSeparator)) && !filepath.IsAbs(rel)
}

func contains(items []string, wanted string) bool {
	for _, item := range items {
		if item == wanted {
			return true
		}
	}
	return false
}

func leadingDomain(name string) string {
	trimmed := strings.TrimLeft(name, "_")
	if trimmed == "" {
		return ""
	}
	var runes []rune
	for index, char := range []rune(trimmed) {
		if index > 0 && unicode.IsUpper(char) {
			break
		}
		runes = append(runes, unicode.ToLower(char))
	}
	return string(runes)
}
