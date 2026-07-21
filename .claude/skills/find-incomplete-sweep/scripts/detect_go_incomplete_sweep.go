// Produce bounded Go incomplete-sweep leads from active go/types call facts.
//
// This helper intentionally belongs only to find-incomplete-sweep. It resolves
// direct calls to project top-level functions, then considers one deliberately
// narrow shape: a keyed struct-literal argument at the same parameter position
// whose field is consistently present at a strong majority and omitted once.
package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"go/ast"
	"go/constant"
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
)

type arguments struct {
	Target       string
	ProjectRoot  string
	GoExecutable string
	MinCallsites int
	MajorityFrac float64
	MinPresent   int
}

type listedError struct {
	Err string `json:"Err"`
}

type listedPackage struct {
	Dir            string       `json:"Dir"`
	ImportPath     string       `json:"ImportPath"`
	GoFiles        []string     `json:"GoFiles"`
	CgoFiles       []string     `json:"CgoFiles"`
	IgnoredGoFiles []string     `json:"IgnoredGoFiles"`
	InvalidGoFiles []string     `json:"InvalidGoFiles"`
	Export         string       `json:"Export"`
	Error          *listedError `json:"Error"`
}

type sourceRecord struct {
	File string `json:"file"`
	Role string `json:"role"`
}

type deferredRecord struct {
	File   string `json:"file"`
	Line   int    `json:"line"`
	Reason string `json:"reason"`
	Detail string `json:"detail,omitempty"`
}

type presentSite struct {
	File string `json:"file"`
	Line int    `json:"line"`
}

type findingRecord struct {
	Callee         string        `json:"callee"`
	Kwarg          string        `json:"kwarg"`
	OptionPosition int           `json:"option_position"`
	GroupSize      int           `json:"group_size"`
	PresentCount   int           `json:"present_count"`
	MajorityFrac   float64       `json:"majority_frac"`
	Straggler      string        `json:"straggler"`
	PresentSites   []presentSite `json:"present_sites"`
	GatedIn        bool          `json:"gated_in"`
	Value          string        `json:"value"`
	Trajectory     string        `json:"trajectory"`
}

type callSite struct {
	File   string
	Line   int
	Fields map[string]string
}

type callGroup struct {
	Callee         string
	OptionPosition int
	Calls          []callSite
	Unsafe         bool
}

type manifest struct {
	SchemaVersion     int               `json:"schema_version"`
	Band              string            `json:"band"`
	Language          string            `json:"language"`
	Analyzer          string            `json:"analyzer"`
	Status            string            `json:"status"`
	ProjectRoot       string            `json:"project_root"`
	Target            map[string]string `json:"target"`
	ProjectResolution map[string]any    `json:"project_resolution"`
	Scope             map[string]string `json:"scope"`
	Findings          []findingRecord   `json:"findings"`
	GatedOut          []findingRecord   `json:"gated_out"`
	Deferred          []deferredRecord  `json:"deferred"`
	Summary           map[string]int    `json:"summary"`
}

var skippedDirectories = map[string]bool{
	".git": true, ".venv": true, "build": true, "coverage": true,
	"dist": true, "node_modules": true, "reports": true, "test": true,
	"tests": true, "vendor": true,
}

func failed(format string, values ...any) {
	fmt.Fprintf(os.Stderr, "[detect_go_incomplete_sweep] failed: %s\n", fmt.Sprintf(format, values...))
	os.Exit(2)
}

func parseArguments() arguments {
	values := arguments{}
	flag.StringVar(&values.Target, "target", "", "Go file or directory target")
	flag.StringVar(&values.ProjectRoot, "project-root", "", "host project root")
	flag.StringVar(&values.GoExecutable, "go-executable", "go", "Go executable")
	flag.IntVar(&values.MinCallsites, "min-callsites", 4, "minimum resolved callsites")
	flag.Float64Var(&values.MajorityFrac, "majority-frac", 0.75, "required present fraction")
	flag.IntVar(&values.MinPresent, "min-present", 3, "minimum field-present callsites")
	flag.Parse()
	if values.Target == "" || values.ProjectRoot == "" || flag.NArg() != 0 {
		failed("usage: detect_go_incomplete_sweep.go --target <path> --project-root <path> [--min-callsites 4] [--majority-frac 0.75] [--min-present 3]")
	}
	if values.MinCallsites < 2 || values.MinPresent < 1 || values.MajorityFrac <= 0 || values.MajorityFrac > 1 {
		failed("thresholds require min-callsites >= 2, min-present >= 1, and majority-frac in (0, 1]")
	}
	return values
}

func within(root, candidate string) bool {
	rel, err := filepath.Rel(root, candidate)
	return err == nil && (rel == "." || (rel != ".." && !strings.HasPrefix(rel, ".."+string(os.PathSeparator)) && !filepath.IsAbs(rel)))
}

func rel(root, path string) string {
	value, err := filepath.Rel(root, path)
	if err != nil {
		return filepath.ToSlash(path)
	}
	return filepath.ToSlash(value)
}

func hasSymlink(root, candidate string) bool {
	if !within(root, candidate) {
		return true
	}
	value, err := filepath.Rel(root, candidate)
	if err != nil || value == "." {
		return false
	}
	current := root
	for _, part := range strings.Split(value, string(os.PathSeparator)) {
		current = filepath.Join(current, part)
		info, statErr := os.Lstat(current)
		if statErr == nil && info.Mode()&os.ModeSymlink != 0 {
			return true
		}
	}
	return false
}

func inventory(root, target string) ([]sourceRecord, map[string]bool) {
	records := []sourceRecord{}
	selected := map[string]bool{}
	add := func(path string) {
		if strings.ToLower(filepath.Ext(path)) != ".go" {
			return
		}
		fset := token.NewFileSet()
		parsed, err := parser.ParseFile(fset, path, nil, parser.ParseComments|parser.AllErrors|parser.SkipObjectResolution)
		if err != nil {
			failed("malformed Go source %s: %v", rel(root, path), err)
		}
		role := "selected"
		if strings.HasSuffix(strings.ToLower(filepath.Base(path)), "_test.go") {
			role = "excluded_test"
		}
		if ast.IsGenerated(parsed) {
			role = "excluded_generated"
		}
		records = append(records, sourceRecord{File: rel(root, path), Role: role})
		if role == "selected" {
			selected[filepath.Clean(path)] = true
		}
	}
	info, err := os.Lstat(target)
	if err != nil {
		failed("target does not exist: %v", err)
	}
	if info.Mode()&os.ModeSymlink != 0 {
		failed("target must not be a symbolic link: %s", rel(root, target))
	}
	if info.Mode().IsRegular() {
		if strings.ToLower(filepath.Ext(target)) != ".go" {
			failed("target must be a .go file or directory: %s", rel(root, target))
		}
		add(target)
	} else if info.IsDir() {
		err = filepath.WalkDir(target, func(path string, entry os.DirEntry, walkErr error) error {
			if walkErr != nil {
				return walkErr
			}
			if path == target {
				return nil
			}
			if entry.Type()&os.ModeSymlink != 0 {
				// Broad scans never follow a link; direct link targets are rejected
				// by the launcher before this traversal begins.
				return nil
			}
			if entry.IsDir() && skippedDirectories[strings.ToLower(entry.Name())] {
				return filepath.SkipDir
			}
			if entry.Type().IsRegular() {
				add(path)
			}
			return nil
		})
		if err != nil {
			failed("cannot inventory target: %v", err)
		}
	} else {
		failed("target must be a .go file or directory: %s", rel(root, target))
	}
	sort.Slice(records, func(i, j int) bool { return records[i].File < records[j].File })
	return records, selected
}

func listPackages(goExecutable, root string) ([]listedPackage, map[string]string) {
	command := exec.Command(goExecutable, "list", "-deps", "-export", "-json", "-e", "./...")
	command.Dir = root
	var stdout, stderr bytes.Buffer
	command.Stdout, command.Stderr = &stdout, &stderr
	_ = command.Run()
	decoder := json.NewDecoder(&stdout)
	packages := []listedPackage{}
	exports := map[string]string{}
	for {
		var item listedPackage
		err := decoder.Decode(&item)
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			failed("go list emitted malformed package JSON")
		}
		packages = append(packages, item)
		if item.Export != "" {
			exports[item.ImportPath] = item.Export
		}
	}
	if len(packages) == 0 {
		detail := strings.TrimSpace(stderr.String())
		if detail == "" {
			detail = "go list returned no package facts"
		}
		failed("type facts unavailable: %s", detail)
	}
	return packages, exports
}

func exportImporter(fset *token.FileSet, exports map[string]string) types.Importer {
	lookup := func(path string) (io.ReadCloser, error) {
		location := exports[path]
		if location == "" {
			return nil, fmt.Errorf("no export data for %s", path)
		}
		return os.Open(location)
	}
	return importer.ForCompiler(fset, "gc", lookup)
}

func namedStruct(value types.Type) (*types.Struct, bool) {
	if value == nil {
		return nil, false
	}
	if pointer, ok := value.(*types.Pointer); ok {
		value = pointer.Elem()
	}
	if named, ok := value.(*types.Named); ok {
		value = named.Underlying()
	}
	structure, ok := value.Underlying().(*types.Struct)
	return structure, ok
}

func unwrapComposite(expression ast.Expr) *ast.CompositeLit {
	for {
		switch value := expression.(type) {
		case *ast.ParenExpr:
			expression = value.X
		case *ast.UnaryExpr:
			if value.Op != token.AND {
				return nil
			}
			expression = value.X
		case *ast.CompositeLit:
			return value
		default:
			return nil
		}
	}
}

func comparableValue(info *types.Info, expression ast.Expr) (string, bool) {
	value := info.Types[expression].Value
	typeOf := info.TypeOf(expression)
	if value == nil || typeOf == nil {
		return "", false
	}
	typeName := types.TypeString(typeOf, func(pkg *types.Package) string { return pkg.Path() })
	if value.Kind() == constant.String {
		return typeName + ":" + constant.StringVal(value), true
	}
	return typeName + ":" + value.ExactString(), true
}

func literalFields(info *types.Info, literal *ast.CompositeLit, structure *types.Struct) (map[string]string, string) {
	known := map[string]bool{}
	for index := 0; index < structure.NumFields(); index++ {
		known[structure.Field(index).Name()] = true
	}
	fields := map[string]string{}
	for _, element := range literal.Elts {
		pair, ok := element.(*ast.KeyValueExpr)
		if !ok {
			return nil, "unkeyed_struct_literal"
		}
		key, ok := pair.Key.(*ast.Ident)
		if !ok || !known[key.Name] {
			return nil, "unresolved_struct_field"
		}
		if _, duplicate := fields[key.Name]; duplicate {
			return nil, "duplicate_struct_field"
		}
		if value, comparable := comparableValue(info, pair.Value); comparable {
			fields[key.Name] = value
		} else {
			fields[key.Name] = ""
		}
	}
	return fields, ""
}

func directFunction(info *types.Info, expression ast.Expr) (*types.Func, *types.Signature, string) {
	var object types.Object
	switch value := expression.(type) {
	case *ast.Ident:
		object = info.Uses[value]
	case *ast.SelectorExpr:
		object = info.Uses[value.Sel]
	default:
		return nil, nil, "dynamic_or_unresolved_call"
	}
	if function, ok := object.(*types.Func); ok {
		signature, ok := function.Type().(*types.Signature)
		if !ok {
			return nil, nil, "dynamic_or_unresolved_call"
		}
		return function, signature, ""
	}
	if object != nil {
		if signature, ok := object.Type().Underlying().(*types.Signature); ok {
			return nil, signature, "function_value_call"
		}
	}
	if typeOf := info.TypeOf(expression); typeOf != nil {
		if signature, ok := typeOf.Underlying().(*types.Signature); ok {
			return nil, signature, "dynamic_or_unresolved_call"
		}
	}
	return nil, nil, "dynamic_or_unresolved_call"
}

func functionLabel(function *types.Func) string {
	if function.Pkg() == nil {
		return function.Name()
	}
	return function.Pkg().Path() + "." + function.Name()
}

func deferredForCall(deferred *[]deferredRecord, fset *token.FileSet, file string, call *ast.CallExpr, reason string) {
	position := fset.Position(call.Pos())
	*deferred = append(*deferred, deferredRecord{File: file, Line: position.Line, Reason: reason})
}

func hasStructLiteral(info *types.Info, call *ast.CallExpr) bool {
	for _, argument := range call.Args {
		literal := unwrapComposite(argument)
		if literal == nil {
			continue
		}
		if _, ok := namedStruct(info.TypeOf(literal)); ok {
			return true
		}
	}
	return false
}

func collectPackageCalls(root string, fset *token.FileSet, parsed map[string]*ast.File, selected map[string]bool, packagePath string, projectPackages map[string]bool, importer types.Importer, groups map[string]*callGroup, deferred *[]deferredRecord) {
	files := []*ast.File{}
	paths := make([]string, 0, len(parsed))
	for path := range parsed {
		paths = append(paths, path)
		files = append(files, parsed[path])
	}
	sort.Strings(paths)
	sort.Slice(files, func(i, j int) bool {
		return fset.Position(files[i].Pos()).Filename < fset.Position(files[j].Pos()).Filename
	})
	info := &types.Info{
		Types:      map[ast.Expr]types.TypeAndValue{},
		Defs:       map[*ast.Ident]types.Object{},
		Uses:       map[*ast.Ident]types.Object{},
		Selections: map[*ast.SelectorExpr]*types.Selection{},
	}
	config := types.Config{Importer: importer, Error: func(error) {}}
	if _, err := config.Check(packagePath, fset, files, info); err != nil {
		failed("type facts unavailable for %s: %v", packagePath, err)
	}
	for _, path := range paths {
		file := parsed[path]
		if !selected[filepath.Clean(path)] {
			continue
		}
		fileName := rel(root, path)
		ast.Inspect(file, func(node ast.Node) bool {
			call, ok := node.(*ast.CallExpr)
			if !ok {
				return true
			}
			function, signature, reason := directFunction(info, call.Fun)
			if signature == nil {
				if hasStructLiteral(info, call) {
					deferredForCall(deferred, fset, fileName, call, reason)
				}
				return true
			}
			if function == nil {
				if hasStructLiteral(info, call) {
					deferredForCall(deferred, fset, fileName, call, reason)
				}
				return true
			}
			if signature.Recv() != nil {
				if hasStructLiteral(info, call) {
					deferredForCall(deferred, fset, fileName, call, "method_or_interface_call")
				}
				return true
			}
			if function.Pkg() == nil || !projectPackages[function.Pkg().Path()] {
				if hasStructLiteral(info, call) {
					deferredForCall(deferred, fset, fileName, call, "non_project_function")
				}
				return true
			}
			for index := 0; index < signature.Params().Len(); index++ {
				if _, ok := namedStruct(signature.Params().At(index).Type()); !ok {
					continue
				}
				key := functionLabel(function) + "#" + strconv.Itoa(index)
				group := groups[key]
				if group == nil {
					group = &callGroup{Callee: functionLabel(function), OptionPosition: index}
					groups[key] = group
				}
				if index >= len(call.Args) {
					group.Unsafe = true
					deferredForCall(deferred, fset, fileName, call, "missing_struct_option_argument")
					continue
				}
				literal := unwrapComposite(call.Args[index])
				if literal == nil {
					group.Unsafe = true
					deferredForCall(deferred, fset, fileName, call, "non_literal_struct_option_argument")
					continue
				}
				structure, ok := namedStruct(info.TypeOf(literal))
				if !ok {
					group.Unsafe = true
					deferredForCall(deferred, fset, fileName, call, "unresolved_struct_option_argument")
					continue
				}
				fields, fieldReason := literalFields(info, literal, structure)
				if fieldReason != "" {
					group.Unsafe = true
					deferredForCall(deferred, fset, fileName, call, fieldReason)
					continue
				}
				position := fset.Position(call.Pos())
				group.Calls = append(group.Calls, callSite{File: fileName, Line: position.Line, Fields: fields})
			}
			return true
		})
	}
}

func blameTime(root string, site presentSite) (int64, string) {
	command := exec.Command("git", "blame", "--porcelain", "-L", fmt.Sprintf("%d,%d", site.Line, site.Line), "--", filepath.FromSlash(site.File))
	command.Dir = root
	output, err := command.Output()
	if err != nil {
		return 0, "failed"
	}
	for _, line := range strings.Split(string(output), "\n") {
		if strings.HasPrefix(line, "committer-time ") {
			value, err := strconv.ParseInt(strings.TrimPrefix(line, "committer-time "), 10, 64)
			if err == nil {
				return value, "complete"
			}
		}
	}
	return 0, "insufficient"
}

func gitAvailable(root string) bool {
	command := exec.Command("git", "rev-parse", "--is-inside-work-tree")
	command.Dir = root
	output, err := command.Output()
	return err == nil && strings.TrimSpace(string(output)) == "true"
}

func evaluateGroups(root string, groups map[string]*callGroup, values arguments, gitState *string, deferred *[]deferredRecord) ([]findingRecord, []findingRecord) {
	findings := []findingRecord{}
	gatedOut := []findingRecord{}
	keys := make([]string, 0, len(groups))
	for key := range groups {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		group := groups[key]
		if group.Unsafe || len(group.Calls) < values.MinCallsites {
			continue
		}
		threshold := int(values.MajorityFrac*float64(len(group.Calls)) + 0.999999999)
		if threshold < values.MinPresent {
			threshold = values.MinPresent
		}
		fieldSites := map[string][]callSite{}
		for _, call := range group.Calls {
			for field := range call.Fields {
				fieldSites[field] = append(fieldSites[field], call)
			}
		}
		candidateRows := []findingRecord{}
		for field, present := range fieldSites {
			if len(present) == len(group.Calls) || len(present) < threshold {
				continue
			}
			missing := []callSite{}
			for _, call := range group.Calls {
				if _, ok := call.Fields[field]; !ok {
					missing = append(missing, call)
				}
			}
			if len(missing) != 1 {
				*deferred = append(*deferred, deferredRecord{File: group.Calls[0].File, Line: group.Calls[0].Line, Reason: "ambiguous_multiple_stragglers", Detail: group.Callee + " field " + field})
				continue
			}
			value := present[0].Fields[field]
			consistent := value != ""
			for _, site := range present[1:] {
				if site.Fields[field] == "" {
					consistent = false
					break
				}
				if site.Fields[field] != value {
					consistent = false
				}
			}
			if !consistent {
				reason := "incomparable_option_field_value"
				if value != "" {
					reason = "inconsistent_option_field_value"
				}
				*deferred = append(*deferred, deferredRecord{File: missing[0].File, Line: missing[0].Line, Reason: reason, Detail: group.Callee + " field " + field})
				continue
			}
			presentSites := make([]presentSite, 0, len(present))
			for _, site := range present {
				presentSites = append(presentSites, presentSite{File: site.File, Line: site.Line})
			}
			candidateRows = append(candidateRows, findingRecord{
				Callee: group.Callee, Kwarg: field, OptionPosition: group.OptionPosition,
				GroupSize: len(group.Calls), PresentCount: len(present),
				MajorityFrac: float64(len(present)) / float64(len(group.Calls)),
				Straggler:    missing[0].File + ":" + strconv.Itoa(missing[0].Line),
				PresentSites: presentSites, Value: value,
			})
		}
		if len(candidateRows) > 1 {
			*deferred = append(*deferred, deferredRecord{File: group.Calls[0].File, Line: group.Calls[0].Line, Reason: "multiple_option_field_divergences", Detail: group.Callee})
			continue
		}
		if len(candidateRows) != 1 {
			continue
		}
		row := candidateRows[0]
		if !gitAvailable(root) {
			*gitState = "insufficient"
			*deferred = append(*deferred, deferredRecord{File: row.PresentSites[0].File, Line: row.PresentSites[0].Line, Reason: "insufficient_git_evidence", Detail: row.Callee})
			continue
		}
		stragglerFile, stragglerLine, _ := strings.Cut(row.Straggler, ":")
		line, _ := strconv.Atoi(stragglerLine)
		stragglerTime, state := blameTime(root, presentSite{File: stragglerFile, Line: line})
		if state != "complete" {
			*gitState = state
			*deferred = append(*deferred, deferredRecord{File: stragglerFile, Line: line, Reason: state + "_git_evidence", Detail: row.Callee})
			continue
		}
		newer := 0
		failedEvidence := false
		for _, site := range row.PresentSites {
			time, presentState := blameTime(root, site)
			if presentState != "complete" {
				*gitState = presentState
				failedEvidence = true
				break
			}
			if time > stragglerTime {
				newer++
			}
		}
		if failedEvidence {
			*deferred = append(*deferred, deferredRecord{File: stragglerFile, Line: line, Reason: *gitState + "_git_evidence", Detail: row.Callee})
			continue
		}
		if newer == len(row.PresentSites) {
			row.GatedIn = true
			row.Trajectory = fmt.Sprintf("%d/%d option-present sites touched AFTER the straggler — consistent with a sweep that missed it", newer, len(row.PresentSites))
			findings = append(findings, row)
		} else {
			row.Trajectory = fmt.Sprintf("only %d/%d option-present sites touched AFTER the straggler — likely deliberate", newer, len(row.PresentSites))
			gatedOut = append(gatedOut, row)
		}
	}
	return findings, gatedOut
}

func main() {
	values := parseArguments()
	root, err := filepath.Abs(values.ProjectRoot)
	if err != nil {
		failed("cannot resolve project root: %v", err)
	}
	root = filepath.Clean(root)
	info, err := os.Lstat(root)
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		failed("project root is not a directory: %s", values.ProjectRoot)
	}
	target, err := filepath.Abs(values.Target)
	if err != nil || !within(root, target) || hasSymlink(root, target) {
		failed("target must stay inside project root without symbolic links: %s", values.Target)
	}
	records, selected := inventory(root, target)
	packages, exports := listPackages(values.GoExecutable, root)
	projectPackages := map[string]bool{}
	active := map[string]bool{}
	inactive := []string{}
	packageFiles := map[string][]string{}
	packagePaths := map[string]string{}
	for _, item := range packages {
		if item.Dir == "" || !within(root, item.Dir) {
			continue
		}
		projectPackages[item.ImportPath] = true
		for _, name := range item.IgnoredGoFiles {
			path := filepath.Join(item.Dir, name)
			if selected[filepath.Clean(path)] {
				inactive = append(inactive, rel(root, path))
			}
		}
		for _, name := range item.CgoFiles {
			path := filepath.Join(item.Dir, name)
			if selected[filepath.Clean(path)] {
				inactive = append(inactive, rel(root, path))
			}
		}
		files := []string{}
		filteredLinkedSource := false
		for _, name := range item.GoFiles {
			path := filepath.Clean(filepath.Join(item.Dir, name))
			pathInfo, statErr := os.Lstat(path)
			if statErr != nil || pathInfo.Mode()&os.ModeSymlink != 0 || hasSymlink(root, path) {
				// `go list` can enumerate a linked .go file even though the
				// detector's selected traversal correctly ignored it. Keep the
				// package typecheck on real files only; never follow the link.
				filteredLinkedSource = true
				continue
			}
			files = append(files, path)
			if selected[path] {
				active[path] = true
			}
		}
		if len(files) > 0 {
			packageFiles[item.ImportPath] = files
			packagePaths[item.ImportPath] = item.ImportPath
		}
		if item.Error != nil && !filteredLinkedSource {
			for _, name := range item.GoFiles {
				if selected[filepath.Clean(filepath.Join(item.Dir, name))] {
					failed("type facts unavailable for %s: %s", item.ImportPath, item.Error.Err)
				}
			}
		}
	}
	for path := range selected {
		if !active[path] {
			foundInactive := false
			for _, file := range inactive {
				if file == rel(root, path) {
					foundInactive = true
				}
			}
			if !foundInactive {
				inactive = append(inactive, rel(root, path))
			}
		}
	}
	sort.Strings(inactive)
	fset := token.NewFileSet()
	groups := map[string]*callGroup{}
	deferred := []deferredRecord{}
	for packagePath, paths := range packageFiles {
		parsed := map[string]*ast.File{}
		for _, path := range paths {
			file, parseErr := parser.ParseFile(fset, path, nil, parser.ParseComments|parser.AllErrors)
			if parseErr != nil {
				failed("malformed Go source %s: %v", rel(root, path), parseErr)
			}
			parsed[path] = file
		}
		collectPackageCalls(root, fset, parsed, selected, packagePaths[packagePath], projectPackages, exportImporter(fset, exports), groups, &deferred)
	}
	gitState := "complete"
	findings, gatedOut := evaluateGroups(root, groups, values, &gitState, &deferred)
	sort.Slice(findings, func(i, j int) bool { return findings[i].Straggler < findings[j].Straggler })
	sort.Slice(gatedOut, func(i, j int) bool { return gatedOut[i].Straggler < gatedOut[j].Straggler })
	sort.Slice(deferred, func(i, j int) bool {
		if deferred[i].File != deferred[j].File {
			return deferred[i].File < deferred[j].File
		}
		if deferred[i].Line != deferred[j].Line {
			return deferred[i].Line < deferred[j].Line
		}
		return deferred[i].Reason < deferred[j].Reason
	})
	status := "complete"
	if len(inactive) > 0 || gitState != "complete" {
		status = "partial"
	}
	targetInfo, _ := os.Stat(target)
	payload := manifest{
		SchemaVersion: 1, Band: "go-option-omission", Language: "go", Analyzer: "go-list-go-parser-go-types", Status: status,
		ProjectRoot:       root,
		Target:            map[string]string{"path": rel(root, target), "kind": map[bool]string{true: "directory", false: "file"}[targetInfo.IsDir()]},
		ProjectResolution: map[string]any{"state": status, "inactive_files": inactive, "git_evidence": gitState, "source_inventory": records},
		Scope: map[string]string{
			"supported": "Resolved direct calls to project top-level functions with keyed struct option literals and comparable constant field values.",
			"deferred":  "Methods, interface dispatch, function values, dynamic or unresolved calls, non-project calls, unkeyed/dynamic literals, ambiguous stragglers, inconsistent values, inactive builds, and insufficient Git evidence.",
		},
		Findings: findings, GatedOut: gatedOut, Deferred: deferred,
		Summary: map[string]int{"raw_divergence_candidates": len(findings) + len(gatedOut), "gated_in": len(findings), "gated_out": len(gatedOut), "deferred": len(deferred)},
	}
	encoded, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		failed("cannot encode manifest: %v", err)
	}
	fmt.Println(string(encoded))
}
