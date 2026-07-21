// Produce a bounded, read-only Go package map.
//
// Go v1 maps one package directory in one root module for the current active
// build. It uses go list for package/import facts and go/parser/go/ast for
// source inventory, exported declarations, and import spelling. It does not
// use go/packages, go/types, a language server, or a shared runtime.
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
	"regexp"
	"sort"
	"strconv"
	"strings"
)

const defaultMinimumGo = "1.22"

type moduleInfo struct {
	Path      string `json:"Path"`
	Dir       string `json:"Dir"`
	GoVersion string `json:"GoVersion"`
}

type moduleFileInfo struct {
	Replace []json.RawMessage `json:"Replace"`
}

type packageError struct {
	Err string `json:"Err"`
}

type packageInfo struct {
	Dir              string        `json:"Dir"`
	ImportPath       string        `json:"ImportPath"`
	Name             string        `json:"Name"`
	GoFiles          []string      `json:"GoFiles"`
	GeneratedGoFiles []string      `json:"GeneratedGoFiles"`
	CgoFiles         []string      `json:"CgoFiles"`
	IgnoredGoFiles   []string      `json:"IgnoredGoFiles"`
	Imports          []string      `json:"Imports"`
	Error            *packageError `json:"Error"`
	Incomplete       bool          `json:"Incomplete"`
}

type mapTarget struct {
	Path          string   `json:"path"`
	Kind          string   `json:"kind"`
	Package       string   `json:"package,omitempty"`
	ImportPath    string   `json:"import_path,omitempty"`
	SourceFiles   int      `json:"source_files"`
	ExcludedFiles []string `json:"excluded_files"`
}

type sourceFile struct {
	File string `json:"file"`
}

type exportedSymbol struct {
	File     string `json:"file"`
	Line     int    `json:"line"`
	Name     string `json:"name"`
	Kind     string `json:"kind"`
	Receiver string `json:"receiver,omitempty"`
}

type importEdge struct {
	File            string `json:"file"`
	Line            int    `json:"line"`
	ImportPath      string `json:"import_path"`
	LocalName       string `json:"local_name,omitempty"`
	Style           string `json:"style"`
	Resolution      string `json:"resolution"`
	ResolvedPackage string `json:"resolved_package,omitempty"`
}

type inboundEdge struct {
	SourcePackage string `json:"source_package"`
	SourceFile    string `json:"source_file"`
	Line          int    `json:"line"`
	LocalName     string `json:"local_name,omitempty"`
	Style         string `json:"style"`
}

type workflowEntry struct {
	Name         string   `json:"name"`
	Path         string   `json:"path"`
	MatchedPaths []string `json:"matched_paths"`
}

type workflowParticipation struct {
	Availability string          `json:"availability"`
	Reason       string          `json:"reason,omitempty"`
	Entries      []workflowEntry `json:"entries"`
}

type unavailableField struct {
	Field  string `json:"field"`
	Reason string `json:"reason"`
}

type mapPayload struct {
	SchemaVersion         int                    `json:"schema_version"`
	Skill                 string                 `json:"skill"`
	Name                  string                 `json:"name"`
	Language              string                 `json:"language"`
	Analyzer              string                 `json:"analyzer"`
	Status                string                 `json:"status"`
	FailureKind           string                 `json:"failure_kind,omitempty"`
	Message               string                 `json:"message,omitempty"`
	Tooling               map[string]string      `json:"tooling"`
	Module                map[string]string      `json:"module"`
	ActiveBuild           map[string]interface{} `json:"active_build"`
	Target                mapTarget              `json:"target"`
	Completeness          map[string]string      `json:"completeness"`
	Counts                map[string]int         `json:"counts"`
	Files                 []sourceFile           `json:"files"`
	ExportedSurface       []exportedSymbol       `json:"exported_surface"`
	OutboundImports       []importEdge           `json:"outbound_imports"`
	InboundImports        []inboundEdge          `json:"inbound_imports"`
	UnresolvedImports     []importEdge           `json:"unresolved_imports"`
	GraphIssues           []string               `json:"graph_issues"`
	WorkflowParticipation workflowParticipation  `json:"workflow_participation"`
	UnavailableFields     []unavailableField     `json:"unavailable_fields"`
}

type runnerError struct {
	message string
	exit    int
}

func (err *runnerError) Error() string { return err.message }

func main() {
	var target, projectRoot, output, evidence, effectivenessLog, name, minimumGo string
	flag.StringVar(&target, "target", "", "Go package directory within the project root")
	flag.StringVar(&projectRoot, "project-root", ".", "host project root")
	flag.StringVar(&output, "output", "", "durable Markdown map beneath .claude/docs/subsystems/")
	flag.StringVar(&evidence, "evidence", "", "JSON evidence beneath reports/map/")
	flag.StringVar(&effectivenessLog, "effectiveness-log", "", "optional JSONL path beneath reports/_meta/")
	flag.StringVar(&name, "name", "", "durable subsystem map name")
	flag.StringVar(&minimumGo, "minimum-go", defaultMinimumGo, "minimum required Go version")
	flag.Parse()

	if target == "" || output == "" || evidence == "" || name == "" {
		fmt.Fprintln(os.Stderr, "usage: map_go.go --name <name> --target <package-dir> --project-root <root> --output <map.md> --evidence <map.json> [--effectiveness-log <jsonl>]")
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
	outputPath, err := artifactPath(root, output, filepath.Join(".claude", "docs", "subsystems"), "artifact output")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	evidencePath, err := artifactPath(root, evidence, filepath.Join("reports", "map"), "artifact evidence")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	logPath := ""
	if effectivenessLog != "" {
		logPath, err = artifactPath(root, effectivenessLog, filepath.Join("reports", "_meta"), "effectiveness log")
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
	}

	if runErr := run(name, target, root, outputPath, evidencePath, logPath, minimumGo); runErr != nil {
		fmt.Fprintf(os.Stderr, "[map_go] %s\n", runErr.message)
		os.Exit(runErr.exit)
	}
}

func run(name, target, root, output, evidence, effectivenessLog, minimumGo string) *runnerError {
	goPath, err := exec.LookPath("go")
	if err != nil {
		return terminal(name, root, target, output, evidence, "unsupported", "go_tool_missing", "Go was not found on PATH.", 0)
	}
	versionText, err := commandOutput(root, goPath, "version")
	if err != nil {
		return terminal(name, root, target, output, evidence, "unsupported", "go_version_failed", err.Error(), 0)
	}
	version := strings.TrimSpace(versionText)
	if !atLeastGoVersion(version, minimumGo) {
		return terminal(name, root, target, output, evidence, "unsupported", "go_version_too_old", fmt.Sprintf("Go %s is below the required Go %s.", version, minimumGo), 0)
	}
	workspace, err := commandOutput(root, goPath, "env", "GOWORK")
	if err != nil {
		return terminal(name, root, target, output, evidence, "unsupported", "go_workspace_check_failed", err.Error(), 0)
	}
	if trimmed := strings.TrimSpace(workspace); trimmed != "" && trimmed != "off" {
		return terminal(name, root, target, output, evidence, "unsupported", "go_workspace_active", fmt.Sprintf("Go map v1 does not support an active go.work workspace: %s.", trimmed), 0)
	}
	moduleFile, err := goModFacts(root, goPath)
	if err != nil {
		return terminal(name, root, target, output, evidence, "unsupported", "go_module_required", err.Error(), 0)
	}
	if len(moduleFile.Replace) > 0 {
		return terminal(name, root, target, output, evidence, "unsupported", "go_mod_replace", "Go map v1 does not support go.mod replace directives.", 0)
	}
	module, err := moduleFacts(root, goPath)
	if err != nil || module.Path == "" || module.Dir == "" || clean(module.Dir) != clean(root) {
		message := "Go map v1 requires the project root to be one root module."
		if err != nil {
			message = err.Error()
		}
		return terminal(name, root, target, output, evidence, "unsupported", "go_root_module_required", message, 0)
	}

	targetPath, err := projectPath(root, target)
	if err != nil {
		return terminal(name, root, target, output, evidence, "unsupported", "unsafe_target", err.Error(), 0)
	}
	if err := rejectSymlinkPath(root, targetPath); err != nil {
		return terminal(name, root, target, output, evidence, "unsupported", "unsafe_target", err.Error(), 0)
	}
	info, err := os.Stat(targetPath)
	if err != nil {
		return terminal(name, root, target, output, evidence, "unsupported", "target_not_found", err.Error(), 0)
	}
	if !info.IsDir() {
		return terminal(name, root, target, output, evidence, "unsupported", "target_not_package_directory", "Go map v1 accepts one package directory, not an individual file.", 0)
	}
	if excludedDirectory(root, targetPath) {
		return terminal(name, root, target, output, evidence, "unsupported", "excluded_target", "Vendor and testdata directories are outside the Go map v1 source boundary.", 0)
	}

	goos, goarch := goEnvironment(root, goPath)
	packages, listErr := packageFacts(root, goPath)
	selected := findPackage(packages, targetPath)
	if selected == nil {
		message := "go list did not return an active package for the requested directory."
		if listErr != nil {
			message = listErr.Error()
		}
		return terminal(name, root, target, output, evidence, "unsupported", "target_package_unavailable", message, 0)
	}
	if len(selected.CgoFiles) > 0 {
		return terminal(name, root, target, output, evidence, "partial", "cgo_unavailable", "Go map v1 does not map packages with active cgo files.", 0)
	}

	files, exported, outbound, excluded, packageName, parseErr := inspectTarget(root, selected)
	if parseErr != nil {
		return terminal(name, root, target, output, evidence, "failed", "syntax_error", parseErr.Error(), 2)
	}
	if len(files) == 0 {
		return terminal(name, root, target, output, evidence, "unsupported", "no_eligible_go_source", "The target package contains no non-generated active Go source files.", 0)
	}

	issues := []string{}
	if listErr != nil {
		issues = append(issues, listErr.Error())
	}
	if selected.Error != nil && selected.Error.Err != "" {
		issues = append(issues, "target package: "+selected.Error.Err)
	}
	if selected.Incomplete {
		issues = append(issues, "target package is incomplete according to go list")
	}
	if packageName != selected.Name {
		issues = append(issues, fmt.Sprintf("parsed package name %q does not match go list name %q", packageName, selected.Name))
	}

	packageIndex := firstPartyPackageIndex(root, module.Path, packages)
	unresolved := unresolvedFirstParty(outbound, module.Path, packageIndex)
	if len(unresolved) > 0 {
		issues = append(issues, "one or more target imports could not be resolved to an active first-party package")
	}
	inbound, inboundIssues := collectInbound(root, packages, selected.ImportPath)
	issues = append(issues, inboundIssues...)
	workflows := collectWorkflows(root, files)

	status := "complete"
	if len(issues) > 0 {
		status = "partial"
	}
	payload := mapPayload{
		SchemaVersion: 1,
		Skill:         "map-subsystem",
		Name:          name,
		Language:      "go",
		Analyzer:      "go-list-plus-stdlib-ast",
		Status:        status,
		Tooling: map[string]string{
			"go_path": goPath, "go_version": version, "minimum_go_version": minimumGo,
			"package_facts": "go list -e -json -mod=readonly ./...",
			"parser":        "go/parser and go/ast (standard library)",
		},
		Module: map[string]string{"path": module.Path, "go_version": module.GoVersion},
		ActiveBuild: map[string]interface{}{
			"goos": goos, "goarch": goarch,
			"ignored_go_files": relativeFiles(root, selected.Dir, selected.IgnoredGoFiles),
			"scope":            "Current active Go build only; other build tags and GOOS/GOARCH variants are not mapped.",
		},
		Target: mapTarget{
			Path: relative(root, targetPath), Kind: "package_directory", Package: selected.Name,
			ImportPath: selected.ImportPath, SourceFiles: len(files), ExcludedFiles: excluded,
		},
		Completeness: map[string]string{
			"active_build_inventory": "complete", "exported_surface": "complete",
			"first_party_module_edges": completeState(len(issues) == 0),
			"build_matrix":             "unavailable",
			"runtime_dispatch":         "unavailable",
		},
		Counts: map[string]int{
			"source_files": len(files), "exported_symbols": len(exported),
			"outbound_imports": len(outbound), "inbound_imports": len(inbound),
			"unresolved_imports": len(unresolved), "workflow_entries": len(workflows.Entries),
		},
		Files:                 files,
		ExportedSurface:       exported,
		OutboundImports:       outbound,
		InboundImports:        inbound,
		UnresolvedImports:     unresolved,
		GraphIssues:           sortedStrings(issues),
		WorkflowParticipation: workflows,
		UnavailableFields: []unavailableField{
			{Field: "responsibility_clusters", Reason: "Go v1 maps package facts and does not infer responsibility clusters."},
			{Field: "open_questions", Reason: "Go v1 does not generate judgment-oriented open questions."},
			{Field: "call_graph", Reason: "Go v1 does not claim go/types call identity, interface dispatch, reflection, or runtime reachability."},
			{Field: "build_matrix", Reason: "Go v1 records only the current go list build selection."},
			{Field: "lint_policy", Reason: "Go v1 does not infer or execute host lint policy."},
		},
	}
	return writePayload(payload, output, evidence, effectivenessLog, 0)
}

func terminal(name, root, target, output, evidence, status, failureKind, message string, exit int) *runnerError {
	payload := mapPayload{
		SchemaVersion: 1, Skill: "map-subsystem", Name: name, Language: "go",
		Analyzer: "go-list-plus-stdlib-ast", Status: status, FailureKind: failureKind, Message: message,
		Tooling: map[string]string{}, Module: map[string]string{}, ActiveBuild: map[string]interface{}{
			"goos": "unknown", "goarch": "unknown", "ignored_go_files": []string{},
			"scope": "Go map v1 did not reach active-build package analysis.",
		},
		Target:       mapTarget{Path: target, Kind: "package_directory", ExcludedFiles: []string{}},
		Completeness: map[string]string{"active_build_inventory": "unavailable", "exported_surface": "unavailable", "first_party_module_edges": "unavailable", "build_matrix": "unavailable", "runtime_dispatch": "unavailable"},
		Counts:       map[string]int{"source_files": 0, "exported_symbols": 0, "outbound_imports": 0, "inbound_imports": 0, "unresolved_imports": 0, "workflow_entries": 0},
		Files:        []sourceFile{}, ExportedSurface: []exportedSymbol{}, OutboundImports: []importEdge{}, InboundImports: []inboundEdge{}, UnresolvedImports: []importEdge{}, GraphIssues: []string{failureKind},
		WorkflowParticipation: workflowParticipation{Availability: "unavailable", Reason: "Map did not reach package analysis.", Entries: []workflowEntry{}},
		UnavailableFields:     []unavailableField{},
	}
	return writePayload(payload, output, evidence, "", exit)
}

func writePayload(payload mapPayload, output, evidence, effectivenessLog string, exit int) *runnerError {
	encoded, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return &runnerError{message: err.Error(), exit: 2}
	}
	if err := writeAtomic(evidence, append(encoded, '\n')); err != nil {
		return &runnerError{message: err.Error(), exit: 2}
	}
	if err := writeAtomic(output, []byte(renderMap(payload))); err != nil {
		return &runnerError{message: err.Error(), exit: 2}
	}
	if effectivenessLog != "" {
		row, marshalErr := json.Marshal(map[string]interface{}{
			"skill": "map-subsystem", "language": "go", "target": payload.Target.Path,
			"findings_total": payload.Counts["exported_symbols"], "buckets": payload.Counts, "status": payload.Status,
		})
		if marshalErr != nil {
			return &runnerError{message: marshalErr.Error(), exit: 2}
		}
		if err := appendLine(effectivenessLog, append(row, '\n')); err != nil {
			return &runnerError{message: err.Error(), exit: 2}
		}
	}
	fmt.Printf("wrote %s and %s (%s)\n", output, evidence, payload.Status)
	if exit != 0 {
		return &runnerError{message: fmt.Sprintf("map stopped: %s", payload.FailureKind), exit: exit}
	}
	return nil
}

func renderMap(payload mapPayload) string {
	lines := []string{
		"---", fmt.Sprintf("subsystem: %s", payload.Name), fmt.Sprintf("target: %s", payload.Target.Path),
		"language: go", fmt.Sprintf("status: %s", payload.Status), fmt.Sprintf("source_files: %d", payload.Counts["source_files"]),
		fmt.Sprintf("exported_symbols: %d", payload.Counts["exported_symbols"]), "---", "",
		fmt.Sprintf("# %s", payload.Name), "", fmt.Sprintf("Status: **%s**. Active-build Go package map using `go list -e -json -mod=readonly ./...` and `go/parser`/`go/ast`.", payload.Status),
	}
	if payload.Message != "" {
		lines = append(lines, "", "## Status detail", "", payload.Message)
	}
	lines = append(lines, "", "## Active build", "", fmt.Sprintf("- GOOS/GOARCH: `%v/%v`", payload.ActiveBuild["goos"], payload.ActiveBuild["goarch"]), "- Scope: Current active Go build only; alternate build tags and build matrices are unavailable.")
	if ignored, ok := payload.ActiveBuild["ignored_go_files"].([]string); ok && len(ignored) > 0 {
		for _, file := range ignored {
			lines = append(lines, fmt.Sprintf("- Ignored by current build: `%s`", file))
		}
	}
	lines = append(lines, "", "## Counts", "", "| Source files | Exported symbols | Outbound imports | Inbound imports | Unresolved first-party imports | Workflow entries |", "|--:|--:|--:|--:|--:|--:|", fmt.Sprintf("| %d | %d | %d | %d | %d | %d |", payload.Counts["source_files"], payload.Counts["exported_symbols"], payload.Counts["outbound_imports"], payload.Counts["inbound_imports"], payload.Counts["unresolved_imports"], payload.Counts["workflow_entries"]))
	lines = append(lines, "", "## Files", "")
	if len(payload.Files) == 0 {
		lines = append(lines, "None.")
	}
	for _, file := range payload.Files {
		lines = append(lines, fmt.Sprintf("- `%s`", file.File))
	}
	lines = append(lines, "", "## Exported surface", "")
	if len(payload.ExportedSurface) == 0 {
		lines = append(lines, "None.")
	}
	for _, symbol := range payload.ExportedSurface {
		receiver := ""
		if symbol.Receiver != "" {
			receiver = fmt.Sprintf(" receiver `%s`", symbol.Receiver)
		}
		lines = append(lines, fmt.Sprintf("- `%s` — `%s` (%s%s)", symbol.File, symbol.Name, symbol.Kind, receiver))
	}
	lines = append(lines, "", "## First-party outbound imports", "")
	firstPartyOutbound := 0
	for _, edge := range payload.OutboundImports {
		if edge.Resolution != "first_party" && edge.Resolution != "unresolved_first_party" {
			continue
		}
		firstPartyOutbound++
		resolved := edge.ResolvedPackage
		if resolved == "" {
			resolved = edge.Resolution
		}
		lines = append(lines, fmt.Sprintf("- `%s:%d` — `%s` → `%s` (%s)", edge.File, edge.Line, edge.ImportPath, resolved, edge.Style))
	}
	if firstPartyOutbound == 0 {
		lines = append(lines, "None.")
	}
	lines = append(lines, "", "## First-party inbound imports", "")
	if len(payload.InboundImports) == 0 {
		lines = append(lines, "None.")
	}
	for _, edge := range payload.InboundImports {
		lines = append(lines, fmt.Sprintf("- `%s:%d` from `%s` (%s)", edge.SourceFile, edge.Line, edge.SourcePackage, edge.Style))
	}
	lines = append(lines, "", "## Workflow participation", "")
	if payload.WorkflowParticipation.Availability == "unavailable" {
		lines = append(lines, "Unavailable: "+payload.WorkflowParticipation.Reason)
	} else if len(payload.WorkflowParticipation.Entries) == 0 {
		lines = append(lines, "No workflow map references the selected source files.")
	} else {
		for _, entry := range payload.WorkflowParticipation.Entries {
			lines = append(lines, fmt.Sprintf("- `%s` — %s", entry.Path, codeList(entry.MatchedPaths)))
		}
	}
	lines = append(lines, "", "## Completeness", "")
	for _, key := range []string{"active_build_inventory", "exported_surface", "first_party_module_edges", "build_matrix", "runtime_dispatch"} {
		lines = append(lines, fmt.Sprintf("- `%s`: %s", key, payload.Completeness[key]))
	}
	if len(payload.GraphIssues) > 0 {
		lines = append(lines, "", "## Incomplete package facts", "")
		for _, issue := range payload.GraphIssues {
			lines = append(lines, "- "+issue)
		}
	}
	lines = append(lines, "", "## Unavailable fields", "")
	if len(payload.UnavailableFields) == 0 {
		lines = append(lines, "No additional unavailable fields were recorded.")
	}
	for _, field := range payload.UnavailableFields {
		lines = append(lines, fmt.Sprintf("- `%s` — %s", field.Field, field.Reason))
	}
	lines = append(lines, "", "## How to regenerate", "", "Run the documented Go map command from the root of one Go module.", "")
	return strings.Join(lines, "\n")
}

func inspectTarget(root string, selected *packageInfo) ([]sourceFile, []exportedSymbol, []importEdge, []string, string, error) {
	fset := token.NewFileSet()
	files := []sourceFile{}
	exported := []exportedSymbol{}
	outbound := []importEdge{}
	excluded := []string{}
	packageName := ""
	for _, name := range selected.GoFiles {
		path := filepath.Join(selected.Dir, name)
		parsed, err := parser.ParseFile(fset, path, nil, parser.ParseComments|parser.AllErrors)
		if err != nil {
			return nil, nil, nil, nil, "", fmt.Errorf("Go syntax error in %s: %w", relative(root, path), err)
		}
		if ast.IsGenerated(parsed) {
			excluded = append(excluded, relative(root, path)+":generated")
			continue
		}
		if packageName == "" {
			packageName = parsed.Name.Name
		} else if packageName != parsed.Name.Name {
			return nil, nil, nil, nil, "", fmt.Errorf("multiple package names in target: %s and %s", packageName, parsed.Name.Name)
		}
		files = append(files, sourceFile{File: relative(root, path)})
		exported = append(exported, collectExports(fset, root, path, parsed)...)
		outbound = append(outbound, collectImports(fset, root, path, parsed)...)
	}
	for _, name := range selected.GeneratedGoFiles {
		candidate := relative(root, filepath.Join(selected.Dir, name)) + ":generated"
		if !contains(excluded, candidate) {
			excluded = append(excluded, candidate)
		}
	}
	sort.Slice(files, func(i, j int) bool { return files[i].File < files[j].File })
	sort.Slice(exported, func(i, j int) bool {
		return exported[i].Name < exported[j].Name || (exported[i].Name == exported[j].Name && exported[i].File < exported[j].File)
	})
	sort.Slice(outbound, func(i, j int) bool {
		return outbound[i].File < outbound[j].File || (outbound[i].File == outbound[j].File && outbound[i].Line < outbound[j].Line)
	})
	return files, exported, outbound, sortedStrings(excluded), packageName, nil
}

func collectExports(fset *token.FileSet, root, path string, file *ast.File) []exportedSymbol {
	items := []exportedSymbol{}
	position := func(node ast.Node) int { return fset.Position(node.Pos()).Line }
	for _, declaration := range file.Decls {
		switch typed := declaration.(type) {
		case *ast.FuncDecl:
			if typed.Name == nil || !token.IsExported(typed.Name.Name) {
				continue
			}
			kind := "function"
			receiver := ""
			if typed.Recv != nil && len(typed.Recv.List) > 0 {
				kind = "method"
				receiver = exprText(typed.Recv.List[0].Type)
			}
			items = append(items, exportedSymbol{File: relative(root, path), Line: position(typed.Name), Name: typed.Name.Name, Kind: kind, Receiver: receiver})
		case *ast.GenDecl:
			for _, spec := range typed.Specs {
				switch value := spec.(type) {
				case *ast.TypeSpec:
					if token.IsExported(value.Name.Name) {
						items = append(items, exportedSymbol{File: relative(root, path), Line: position(value.Name), Name: value.Name.Name, Kind: "type"})
					}
				case *ast.ValueSpec:
					kind := "variable"
					if typed.Tok == token.CONST {
						kind = "constant"
					}
					for _, name := range value.Names {
						if token.IsExported(name.Name) {
							items = append(items, exportedSymbol{File: relative(root, path), Line: position(name), Name: name.Name, Kind: kind})
						}
					}
				}
			}
		}
	}
	return items
}

func collectImports(fset *token.FileSet, root, path string, file *ast.File) []importEdge {
	edges := []importEdge{}
	for _, spec := range file.Imports {
		importPath, err := strconv.Unquote(spec.Path.Value)
		if err != nil {
			continue
		}
		style, local := "default", ""
		if spec.Name != nil {
			local = spec.Name.Name
			switch local {
			case ".":
				style = "dot"
			case "_":
				style = "blank"
			default:
				style = "alias"
			}
		}
		edges = append(edges, importEdge{File: relative(root, path), Line: fset.Position(spec.Pos()).Line, ImportPath: importPath, LocalName: local, Style: style})
	}
	return edges
}

func firstPartyPackageIndex(root, modulePath string, packages []packageInfo) map[string]packageInfo {
	index := map[string]packageInfo{}
	for _, item := range packages {
		if item.ImportPath == "" || !isFirstParty(modulePath, item.ImportPath) || !isWithin(root, item.Dir) {
			continue
		}
		index[item.ImportPath] = item
	}
	return index
}

func unresolvedFirstParty(edges []importEdge, modulePath string, index map[string]packageInfo) []importEdge {
	rows := []importEdge{}
	for indexEdge := range edges {
		edge := &edges[indexEdge]
		if !isFirstParty(modulePath, edge.ImportPath) {
			edge.Resolution = "external_or_standard"
			continue
		}
		if target, ok := index[edge.ImportPath]; ok && target.Error == nil && !target.Incomplete {
			edge.Resolution = "first_party"
			edge.ResolvedPackage = target.ImportPath
			continue
		}
		edge.Resolution = "unresolved_first_party"
		rows = append(rows, *edge)
	}
	return rows
}

func collectInbound(root string, packages []packageInfo, targetImport string) ([]inboundEdge, []string) {
	edges := []inboundEdge{}
	issues := []string{}
	for _, item := range packages {
		if item.ImportPath == "" || item.ImportPath == targetImport || item.Error != nil || item.Incomplete || len(item.CgoFiles) > 0 {
			if item.ImportPath != "" && item.ImportPath != targetImport && (item.Error != nil || item.Incomplete || len(item.CgoFiles) > 0) && contains(item.Imports, targetImport) {
				issues = append(issues, "inbound package facts unavailable for "+item.ImportPath)
			}
			continue
		}
		for _, name := range item.GoFiles {
			path := filepath.Join(item.Dir, name)
			fset := token.NewFileSet()
			parsed, err := parser.ParseFile(fset, path, nil, parser.ParseComments|parser.AllErrors)
			if err != nil {
				issues = append(issues, fmt.Sprintf("cannot parse inbound package %s: %v", item.ImportPath, err))
				continue
			}
			if ast.IsGenerated(parsed) {
				continue
			}
			for _, edge := range collectImports(fset, root, path, parsed) {
				if edge.ImportPath == targetImport {
					edges = append(edges, inboundEdge{SourcePackage: item.ImportPath, SourceFile: edge.File, Line: edge.Line, LocalName: edge.LocalName, Style: edge.Style})
				}
			}
		}
	}
	sort.Slice(edges, func(i, j int) bool {
		return edges[i].SourceFile < edges[j].SourceFile || (edges[i].SourceFile == edges[j].SourceFile && edges[i].Line < edges[j].Line)
	})
	return edges, sortedStrings(issues)
}

func collectWorkflows(root string, files []sourceFile) workflowParticipation {
	workflowRoot := filepath.Join(root, ".claude", "docs", "workflows")
	info, err := os.Stat(workflowRoot)
	if err != nil || !info.IsDir() {
		return workflowParticipation{Availability: "unavailable", Reason: "No .claude/docs/workflows directory exists in this host.", Entries: []workflowEntry{}}
	}
	targets := []string{}
	for _, file := range files {
		targets = append(targets, file.File)
	}
	entries := []workflowEntry{}
	_ = filepath.WalkDir(workflowRoot, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil || entry.Type()&os.ModeSymlink != 0 || entry.IsDir() || filepath.Ext(path) != ".md" {
			return nil
		}
		contents, readErr := os.ReadFile(path)
		if readErr != nil {
			return nil
		}
		matched := []string{}
		for _, target := range targets {
			if strings.Contains(string(contents), target) {
				matched = append(matched, target)
			}
		}
		if len(matched) > 0 {
			entries = append(entries, workflowEntry{Name: strings.TrimSuffix(filepath.Base(path), ".md"), Path: relative(root, path), MatchedPaths: matched})
		}
		return nil
	})
	sort.Slice(entries, func(i, j int) bool { return entries[i].Path < entries[j].Path })
	return workflowParticipation{Availability: "available", Entries: entries}
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

func goModFacts(root, goPath string) (moduleFileInfo, error) {
	output, err := commandOutput(root, goPath, "mod", "edit", "-json")
	if err != nil {
		return moduleFileInfo{}, err
	}
	var facts moduleFileInfo
	if err := json.Unmarshal([]byte(output), &facts); err != nil {
		return moduleFileInfo{}, err
	}
	return facts, nil
}

func packageFacts(root, goPath string) ([]packageInfo, error) {
	command := exec.Command(goPath, "list", "-e", "-json", "-mod=readonly", "./...")
	command.Dir = root
	var stdout, stderr bytes.Buffer
	command.Stdout = &stdout
	command.Stderr = &stderr
	runErr := command.Run()
	decoder := json.NewDecoder(bytes.NewReader(stdout.Bytes()))
	packages := []packageInfo{}
	for {
		var item packageInfo
		err := decoder.Decode(&item)
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return packages, err
		}
		packages = append(packages, item)
	}
	if len(packages) == 0 {
		if runErr != nil {
			return nil, fmt.Errorf("go list failed: %s", strings.TrimSpace(stderr.String()))
		}
		return nil, errors.New("go list returned no package facts")
	}
	if runErr != nil {
		return packages, fmt.Errorf("go list reported incomplete package facts: %s", strings.TrimSpace(stderr.String()))
	}
	return packages, nil
}

func findPackage(packages []packageInfo, directory string) *packageInfo {
	for index := range packages {
		if clean(packages[index].Dir) == clean(directory) {
			return &packages[index]
		}
	}
	return nil
}

func goEnvironment(root, goPath string) (string, string) {
	output, err := commandOutput(root, goPath, "env", "GOOS", "GOARCH")
	if err != nil {
		return "unknown", "unknown"
	}
	values := strings.Fields(output)
	if len(values) != 2 {
		return "unknown", "unknown"
	}
	return values[0], values[1]
}

func commandOutput(directory, executable string, args ...string) (string, error) {
	command := exec.Command(executable, args...)
	command.Dir = directory
	output, err := command.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("%s %s: %s", executable, strings.Join(args, " "), strings.TrimSpace(string(output)))
	}
	return string(output), nil
}

func atLeastGoVersion(versionText, minimum string) bool {
	re := regexp.MustCompile(`go([0-9]+)\.([0-9]+)(?:\.([0-9]+))?`)
	actual := re.FindStringSubmatch(versionText)
	required := re.FindStringSubmatch("go" + minimum)
	if len(actual) == 0 || len(required) == 0 {
		return false
	}
	for index := 1; index <= 3; index++ {
		left, _ := strconv.Atoi(actual[index])
		right, _ := strconv.Atoi(required[index])
		if left != right {
			return left > right
		}
	}
	return true
}

func artifactPath(root, supplied, allowedRelative, label string) (string, error) {
	path, err := projectPath(root, supplied)
	if err != nil {
		return "", fmt.Errorf("%s %w", label, err)
	}
	allowedRoot := filepath.Join(root, allowedRelative)
	if !isWithin(allowedRoot, path) || clean(path) == clean(allowedRoot) {
		return "", fmt.Errorf("%s must stay beneath %s", label, allowedRelative+string(filepath.Separator))
	}
	if err := rejectSymlinkPath(root, path); err != nil {
		return "", fmt.Errorf("%s %w", label, err)
	}
	return path, nil
}

func projectPath(root, supplied string) (string, error) {
	candidate := supplied
	if !filepath.IsAbs(candidate) {
		candidate = filepath.Join(root, candidate)
	}
	candidate = filepath.Clean(candidate)
	if !isWithin(root, candidate) {
		return "", fmt.Errorf("must stay inside project root: %s", supplied)
	}
	return candidate, nil
}

func rejectSymlinkPath(root, candidate string) error {
	if !isWithin(root, candidate) {
		return fmt.Errorf("must stay inside project root: %s", candidate)
	}
	rootInfo, err := os.Lstat(root)
	if err != nil {
		return err
	}
	if rootInfo.Mode()&os.ModeSymlink != 0 {
		return fmt.Errorf("must not traverse a symbolic link: %s", root)
	}
	relativePath, err := filepath.Rel(root, candidate)
	if err != nil {
		return err
	}
	current := root
	for _, part := range strings.Split(relativePath, string(filepath.Separator)) {
		if part == "." || part == "" {
			continue
		}
		current = filepath.Join(current, part)
		info, lstatErr := os.Lstat(current)
		if os.IsNotExist(lstatErr) {
			return nil
		}
		if lstatErr != nil {
			return lstatErr
		}
		if info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("must not traverse a symbolic link: %s", candidate)
		}
	}
	return nil
}

func excludedDirectory(root, candidate string) bool {
	relativePath := relative(root, candidate)
	for _, part := range strings.Split(relativePath, "/") {
		if part == "vendor" || part == "testdata" {
			return true
		}
	}
	return false
}

func writeAtomic(path string, contents []byte) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	temporary := fmt.Sprintf("%s.tmp-%d", path, os.Getpid())
	if err := os.WriteFile(temporary, contents, 0644); err != nil {
		return err
	}
	return os.Rename(temporary, path)
}

func appendLine(path string, line []byte) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	file, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return err
	}
	defer file.Close()
	_, err = file.Write(line)
	return err
}

func relative(root, path string) string {
	relativePath, err := filepath.Rel(root, path)
	if err != nil {
		return path
	}
	return filepath.ToSlash(relativePath)
}

func relativeFiles(root, directory string, names []string) []string {
	files := []string{}
	for _, name := range names {
		files = append(files, relative(root, filepath.Join(directory, name)))
	}
	return sortedStrings(files)
}

func isWithin(root, candidate string) bool {
	relativePath, err := filepath.Rel(clean(root), clean(candidate))
	if err != nil {
		return false
	}
	return relativePath == "." || (relativePath != ".." && !strings.HasPrefix(relativePath, ".."+string(filepath.Separator)) && !filepath.IsAbs(relativePath))
}

func clean(path string) string {
	return filepath.Clean(path)
}

func isFirstParty(modulePath, importPath string) bool {
	return importPath == modulePath || strings.HasPrefix(importPath, modulePath+"/")
}

func completeState(complete bool) string {
	if complete {
		return "complete"
	}
	return "partial"
}

func sortedStrings(values []string) []string {
	copyValues := append([]string{}, values...)
	sort.Strings(copyValues)
	return copyValues
}

func contains(values []string, wanted string) bool {
	for _, value := range values {
		if value == wanted {
			return true
		}
	}
	return false
}

func exprText(expression ast.Expr) string {
	switch typed := expression.(type) {
	case *ast.Ident:
		return typed.Name
	case *ast.StarExpr:
		return "*" + exprText(typed.X)
	case *ast.IndexExpr:
		return exprText(typed.X)
	case *ast.IndexListExpr:
		return exprText(typed.X)
	case *ast.SelectorExpr:
		return exprText(typed.X) + "." + typed.Sel.Name
	default:
		return "syntax"
	}
}

func codeList(values []string) string {
	items := []string{}
	for _, value := range values {
		items = append(items, "`"+value+"`")
	}
	return strings.Join(items, ", ")
}
