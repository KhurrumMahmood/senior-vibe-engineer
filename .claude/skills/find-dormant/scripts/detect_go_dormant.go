// Extract conservative active-build Go dormant-code facts for find-dormant.
//
// This helper is intentionally family-local. It batches package selection,
// parsing, and go/types use resolution for the requested target. It reports
// only package-level, unexported functions and function-valued variables; it
// never establishes runtime reachability or safe deletion.
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
	"runtime"
	"sort"
	"strconv"
	"strings"
)

var skipDirectories = map[string]bool{
	".git": true, ".venv": true, "build": true, "coverage": true,
	"dependencies": true, "deps": true, "dist": true, "fixture": true,
	"fixtures": true, "gen": true, "generated": true, "node_modules": true,
	"out": true, "reports": true, "test": true, "testdata": true,
	"tests": true, "third-party": true, "third_party": true, "vendor": true,
}

var goos = map[string]bool{
	"aix": true, "android": true, "darwin": true, "dragonfly": true,
	"freebsd": true, "illumos": true, "ios": true, "js": true,
	"linux": true, "netbsd": true, "openbsd": true, "plan9": true,
	"solaris": true, "wasip1": true, "windows": true,
}

var goarch = map[string]bool{
	"386": true, "amd64": true, "arm": true, "arm64": true,
	"loong64": true, "mips": true, "mips64": true, "mips64le": true,
	"mipsle": true, "ppc64": true, "ppc64le": true, "riscv64": true,
	"s390x": true, "wasm": true,
}

type arguments struct {
	Target       string
	ProjectRoot  string
	GoExecutable string
}

type listedError struct {
	Err string `json:"Err"`
}

type listedPackage struct {
	Dir        string       `json:"Dir"`
	ImportPath string       `json:"ImportPath"`
	GoFiles    []string     `json:"GoFiles"`
	CgoFiles   []string     `json:"CgoFiles"`
	SFiles     []string     `json:"SFiles"`
	Export     string       `json:"Export"`
	Error      *listedError `json:"Error"`
}

type sourceMeta struct {
	Path        string
	Relative    string
	File        *ast.File
	Generated   bool
	Constrained bool
	Target      bool
}

type packageStatus struct {
	Directory  string `json:"directory"`
	ImportPath string `json:"import_path"`
	Status     string `json:"status"`
	Detail     string `json:"detail,omitempty"`
}

type candidate struct {
	ID               string   `json:"id"`
	File             string   `json:"file"`
	Line             int      `json:"line"`
	Name             string   `json:"name"`
	Kind             string   `json:"kind"`
	StaticReferences int      `json:"static_references"`
	Verdict          string   `json:"verdict"`
	Recommendation   string   `json:"recommendation"`
	Uncertainty      []string `json:"uncertainty"`
	Object           types.Object
}

type uncertainSymbol struct {
	File    string `json:"file"`
	Line    int    `json:"line"`
	Name    string `json:"name"`
	Kind    string `json:"kind"`
	Reason  string `json:"reason"`
	Verdict string `json:"verdict"`
}

type uncertaintyFlag struct {
	Kind     string   `json:"kind"`
	Packages []string `json:"packages"`
	Message  string   `json:"message"`
}

type unavailableFile struct {
	File   string `json:"file"`
	Reason string `json:"reason"`
}

type output struct {
	SchemaVersion     int               `json:"schema_version"`
	Language          string            `json:"language"`
	Analyzer          string            `json:"analyzer"`
	Status            string            `json:"status"`
	Target            map[string]string `json:"target"`
	GoVersion         string            `json:"go_version"`
	ProjectResolution map[string]any    `json:"project_resolution"`
	SourceInventory   map[string]int    `json:"source_inventory"`
	Packages          []packageStatus   `json:"packages"`
	Scope             map[string]string `json:"scope"`
	Candidates        []candidate       `json:"candidates"`
	UncertainSymbols  []uncertainSymbol `json:"uncertain_symbols"`
	UncertaintyFlags  []uncertaintyFlag `json:"uncertainty_flags"`
	Summary           map[string]int    `json:"summary"`
}

func fatal(format string, values ...any) {
	fmt.Fprintf(os.Stderr, "[detect_go_dormant] %s\n", fmt.Sprintf(format, values...))
	os.Exit(2)
}

func parseArguments() arguments {
	values := arguments{}
	flag.StringVar(&values.Target, "target", "", "Go file or directory target")
	flag.StringVar(&values.ProjectRoot, "project-root", "", "host project root")
	flag.StringVar(&values.GoExecutable, "go-executable", "go", "Go executable")
	flag.Parse()
	if values.Target == "" || values.ProjectRoot == "" || flag.NArg() != 0 {
		fatal("usage: detect_go_dormant.go --target <path> --project-root <path> [--go-executable <path>]")
	}
	return values
}

func within(root, candidate string) bool {
	relative, err := filepath.Rel(root, candidate)
	if err != nil {
		return false
	}
	return relative == "." || (!strings.HasPrefix(relative, ".."+string(os.PathSeparator)) && relative != ".." && !filepath.IsAbs(relative))
}

func absoluteWithin(root, value, label string) string {
	candidate, err := filepath.Abs(value)
	if err != nil {
		fatal("cannot resolve %s: %v", label, err)
	}
	if !within(root, candidate) {
		fatal("%s must stay inside project root: %s", label, value)
	}
	return candidate
}

func relative(root, path string) string {
	value, err := filepath.Rel(root, path)
	if err != nil {
		return filepath.ToSlash(path)
	}
	return filepath.ToSlash(value)
}

func excluded(root, path string) bool {
	rel, err := filepath.Rel(root, path)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(os.PathSeparator)) {
		return true
	}
	parts := strings.Split(filepath.ToSlash(rel), "/")
	for _, part := range parts[:max(0, len(parts)-1)] {
		if skipDirectories[strings.ToLower(part)] {
			return true
		}
	}
	name := strings.ToLower(filepath.Base(path))
	return strings.HasSuffix(name, "_test.go") || strings.HasSuffix(name, ".generated.go") || strings.HasSuffix(name, "_generated.go")
}

func constrainedFilename(path string) bool {
	name := strings.TrimSuffix(filepath.Base(path), ".go")
	name = strings.TrimSuffix(name, "_test")
	parts := strings.Split(name, "_")
	if len(parts) < 2 {
		return false
	}
	last := parts[len(parts)-1]
	return goos[last] || goarch[last]
}

func hasBuildConstraint(file *ast.File) bool {
	for _, group := range file.Comments {
		if group.End() >= file.Package {
			continue
		}
		for _, comment := range group.List {
			text := strings.TrimSpace(comment.Text)
			if strings.HasPrefix(text, "//go:build") || strings.HasPrefix(text, "// +build") {
				return true
			}
		}
	}
	return false
}

func parseSource(root, path string, target bool) *sourceMeta {
	fset := token.NewFileSet()
	parsed, err := parser.ParseFile(fset, path, nil, parser.ParseComments|parser.AllErrors|parser.SkipObjectResolution)
	if err != nil {
		fatal("syntax-error in %s: %v", relative(root, path), err)
	}
	return &sourceMeta{
		Path: path, Relative: relative(root, path), File: parsed,
		Generated: ast.IsGenerated(parsed), Constrained: hasBuildConstraint(parsed) || constrainedFilename(path), Target: target,
	}
}

func collectTarget(root, target string) (map[string]*sourceMeta, map[string]int) {
	stats, err := os.Lstat(target)
	if err != nil {
		fatal("target does not exist: %v", err)
	}
	if stats.Mode()&os.ModeSymlink != 0 {
		fatal("target must not be a symbolic link: %s", target)
	}
	metas := map[string]*sourceMeta{}
	inventory := map[string]int{"go_candidates": 0, "policy_excluded": 0, "generated": 0}
	add := func(path string) {
		if strings.ToLower(filepath.Ext(path)) != ".go" {
			return
		}
		inventory["go_candidates"]++
		if excluded(root, path) {
			inventory["policy_excluded"]++
			return
		}
		meta := parseSource(root, path, true)
		if meta.Generated {
			inventory["generated"]++
		}
		metas[path] = meta
	}
	if stats.Mode().IsRegular() {
		if strings.ToLower(filepath.Ext(target)) != ".go" {
			fatal("target must be a .go file or directory: %s", target)
		}
		add(target)
		return metas, inventory
	}
	if !stats.IsDir() {
		fatal("target must be a .go file or directory: %s", target)
	}
	err = filepath.WalkDir(target, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if path == target {
			return nil
		}
		if entry.Type()&os.ModeSymlink != 0 {
			if entry.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}
		if entry.IsDir() {
			if excluded(root, filepath.Join(path, "placeholder.go")) {
				return filepath.SkipDir
			}
			return nil
		}
		if entry.Type().IsRegular() {
			add(path)
		}
		return nil
	})
	if err != nil {
		fatal("cannot inventory target: %v", err)
	}
	return metas, inventory
}

func listPackages(goExecutable, root string) ([]listedPackage, string) {
	command := exec.Command(goExecutable, "list", "-deps", "-export", "-json", "-e", "./...")
	command.Dir = root
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	command.Stdout = &stdout
	command.Stderr = &stderr
	_ = command.Run()
	decoder := json.NewDecoder(&stdout)
	packages := []listedPackage{}
	for {
		var item listedPackage
		err := decoder.Decode(&item)
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return packages, "go list emitted malformed package JSON"
		}
		packages = append(packages, item)
	}
	if len(packages) == 0 {
		message := strings.TrimSpace(stderr.String())
		if message == "" {
			message = "go list returned no package facts"
		}
		return packages, message
	}
	return packages, strings.TrimSpace(stderr.String())
}

func sourceFor(root string, known map[string]*sourceMeta, path string) *sourceMeta {
	if meta, found := known[path]; found {
		return meta
	}
	if excluded(root, path) {
		return nil
	}
	meta := parseSource(root, path, false)
	known[path] = meta
	return meta
}

func imports(file *ast.File, path string) bool {
	for _, spec := range file.Imports {
		value := strings.Trim(spec.Path.Value, "\"")
		if value == path {
			return true
		}
	}
	return false
}

func packageName(root, directory string) string {
	return relative(root, directory)
}

func exportImporter(fset *token.FileSet, exports map[string]string) types.Importer {
	lookup := func(path string) (io.ReadCloser, error) {
		location, found := exports[path]
		if !found || location == "" {
			return nil, fmt.Errorf("no export data for %s", path)
		}
		return os.Open(location)
	}
	return importer.ForCompiler(fset, "gc", lookup)
}

func candidateKind(object types.Object) string {
	if _, ok := object.(*types.Func); ok {
		return "function"
	}
	return "variable_function"
}

func isFunctionVariable(object types.Object) bool {
	variable, ok := object.(*types.Var)
	if !ok {
		return false
	}
	_, ok = variable.Type().Underlying().(*types.Signature)
	return ok
}

func stringsAndLinknames(files []*sourceMeta) (map[string]bool, map[string]bool) {
	stringsSeen := map[string]bool{}
	linknames := map[string]bool{}
	for _, meta := range files {
		for _, group := range meta.File.Comments {
			for _, comment := range group.List {
				if strings.Contains(comment.Text, "go:linkname") {
					for _, token := range strings.Fields(comment.Text) {
						linknames[token] = true
					}
				}
			}
		}
		ast.Inspect(meta.File, func(node ast.Node) bool {
			literal, ok := node.(*ast.BasicLit)
			if ok && literal.Kind == token.STRING {
				value, err := strconvUnquote(literal.Value)
				if err == nil {
					stringsSeen[value] = true
				}
			}
			return true
		})
	}
	return stringsSeen, linknames
}

func strconvUnquote(value string) (string, error) {
	if len(value) < 2 {
		return "", errors.New("short string literal")
	}
	if value[0] == '`' && value[len(value)-1] == '`' {
		return value[1 : len(value)-1], nil
	}
	return strconv.Unquote(value)
}

func riskMessages(files []*sourceMeta, generated bool, hasAssembly bool) ([]string, []uncertaintyFlag) {
	flags := []uncertaintyFlag{}
	packageNames := []string{}
	reflectFound := false
	pluginFound := false
	linknameFound := false
	for _, meta := range files {
		packageNames = append(packageNames, meta.Relative)
		reflectFound = reflectFound || imports(meta.File, "reflect")
		pluginFound = pluginFound || imports(meta.File, "plugin")
		for _, group := range meta.File.Comments {
			for _, comment := range group.List {
				linknameFound = linknameFound || strings.Contains(comment.Text, "go:linkname")
			}
		}
	}
	sort.Strings(packageNames)
	messages := []string{"Static analysis cannot establish reflection, //go:linkname, generated registration, plugin, cgo, or assembly reachability."}
	if reflectFound {
		flags = append(flags, uncertaintyFlag{Kind: "reflection", Packages: packageNames, Message: "The package imports reflect; runtime reachability may not appear as an identifier use."})
		messages = append(messages, "The package imports reflect; runtime reachability may not appear as an identifier use.")
	}
	if linknameFound {
		flags = append(flags, uncertaintyFlag{Kind: "linkname", Packages: packageNames, Message: "The package contains //go:linkname; native linkage may bypass normal identifier references."})
		messages = append(messages, "The package contains //go:linkname; native linkage may bypass normal identifier references.")
	}
	if generated {
		flags = append(flags, uncertaintyFlag{Kind: "generated_registration", Packages: packageNames, Message: "Generated Go source was excluded from use resolution and may register or reference symbols."})
		messages = append(messages, "Generated Go source was excluded from use resolution and may register or reference symbols.")
	}
	if pluginFound {
		flags = append(flags, uncertaintyFlag{Kind: "plugin", Packages: packageNames, Message: "The package imports plugin; dynamically loaded code may reach symbols outside static facts."})
		messages = append(messages, "The package imports plugin; dynamically loaded code may reach symbols outside static facts.")
	}
	if hasAssembly {
		flags = append(flags, uncertaintyFlag{Kind: "assembly", Packages: packageNames, Message: "The package contains assembly files; native references are outside go/types use resolution."})
		messages = append(messages, "The package contains assembly files; native references are outside go/types use resolution.")
	}
	return messages, flags
}

func analyzePackage(root string, item listedPackage, targetMetas map[string]*sourceMeta, allMetas map[string]*sourceMeta, exports map[string]string) ([]candidate, []uncertainSymbol, packageStatus, []uncertaintyFlag) {
	directory := filepath.Clean(item.Dir)
	status := packageStatus{Directory: packageName(root, directory), ImportPath: item.ImportPath, Status: "complete"}
	if item.Error != nil && item.Error.Err != "" {
		status.Status = "package-facts-unavailable"
		status.Detail = item.Error.Err
		return nil, nil, status, nil
	}
	if len(item.CgoFiles) > 0 {
		status.Status = "cgo-package-unavailable"
		status.Detail = "cgo files are outside the v1 go/types reachability model"
		return nil, nil, status, []uncertaintyFlag{{Kind: "cgo", Packages: []string{status.Directory}, Message: "The package contains cgo files; cgo reachability is outside the v1 model."}}
	}
	active := []*sourceMeta{}
	generated := false
	constrained := false
	for _, name := range item.GoFiles {
		meta := sourceFor(root, allMetas, filepath.Join(directory, name))
		if meta == nil {
			continue
		}
		if meta.Generated {
			generated = true
			continue
		}
		if meta.Constrained {
			constrained = true
			continue
		}
		active = append(active, meta)
	}
	if constrained {
		status.Status = "build-constraint-ambiguous"
		status.Detail = "an active Go file has a build constraint"
		return nil, nil, status, nil
	}
	if len(active) == 0 {
		status.Status = "package-facts-unavailable"
		status.Detail = "no analyzable active Go source"
		return nil, nil, status, nil
	}
	fset := token.NewFileSet()
	asts := make([]*ast.File, 0, len(active))
	for _, meta := range active {
		parsed, err := parser.ParseFile(fset, meta.Path, nil, parser.ParseComments|parser.AllErrors|parser.SkipObjectResolution)
		if err != nil {
			fatal("syntax-error in %s: %v", meta.Relative, err)
		}
		meta.File = parsed
		asts = append(asts, parsed)
	}
	info := types.Info{Defs: map[*ast.Ident]types.Object{}, Uses: map[*ast.Ident]types.Object{}}
	config := types.Config{Importer: exportImporter(fset, exports)}
	_, err := config.Check(item.ImportPath, fset, asts, &info)
	if err != nil {
		status.Status = "type-facts-unavailable"
		status.Detail = err.Error()
		return nil, nil, status, nil
	}
	packageFiles := append([]*sourceMeta{}, active...)
	for _, meta := range allMetas {
		if filepath.Dir(meta.Path) == directory && meta.Generated {
			generated = true
			packageFiles = append(packageFiles, meta)
		}
	}
	stringsSeen, linknames := stringsAndLinknames(packageFiles)
	messages, flags := riskMessages(active, generated, len(item.SFiles) > 0)
	byObject := map[types.Object]*candidate{}
	for _, meta := range active {
		targetMeta, selected := targetMetas[meta.Path]
		if !selected || !targetMeta.Target {
			continue
		}
		for _, declaration := range meta.File.Decls {
			switch typed := declaration.(type) {
			case *ast.FuncDecl:
				if typed.Recv != nil || typed.Name == nil || typed.Name.Name == "init" || ast.IsExported(typed.Name.Name) {
					continue
				}
				object, ok := info.Defs[typed.Name]
				if !ok {
					continue
				}
				line := fset.PositionFor(typed.Name.Pos(), true).Line
				item := &candidate{ID: candidateID(meta.Relative, typed.Name.Name, line), File: meta.Relative, Line: line, Name: typed.Name.Name, Kind: candidateKind(object), Verdict: "review_required", Recommendation: "human_review_only", Uncertainty: append([]string{}, messages...), Object: object}
				byObject[object] = item
			case *ast.GenDecl:
				if typed.Tok != token.VAR {
					continue
				}
				for _, specification := range typed.Specs {
					value, ok := specification.(*ast.ValueSpec)
					if !ok {
						continue
					}
					for _, name := range value.Names {
						if ast.IsExported(name.Name) {
							continue
						}
						object, ok := info.Defs[name]
						if !ok || !isFunctionVariable(object) {
							continue
						}
						line := fset.PositionFor(name.Pos(), true).Line
						item := &candidate{ID: candidateID(meta.Relative, name.Name, line), File: meta.Relative, Line: line, Name: name.Name, Kind: candidateKind(object), Verdict: "review_required", Recommendation: "human_review_only", Uncertainty: append([]string{}, messages...), Object: object}
						byObject[object] = item
					}
				}
			}
		}
	}
	for _, object := range info.Uses {
		if item, found := byObject[object]; found {
			item.StaticReferences++
		}
	}
	candidates := []candidate{}
	uncertain := []uncertainSymbol{}
	for _, item := range byObject {
		if item.StaticReferences > 0 {
			continue
		}
		if stringsSeen[item.Name] {
			uncertain = append(uncertain, uncertainSymbol{File: item.File, Line: item.Line, Name: item.Name, Kind: item.Kind, Reason: "An exact matching string literal may be reflective or dynamic reachability; static analysis cannot resolve it.", Verdict: "uncertain"})
			continue
		}
		if linknames[item.Name] {
			uncertain = append(uncertain, uncertainSymbol{File: item.File, Line: item.Line, Name: item.Name, Kind: item.Kind, Reason: "A //go:linkname directive may provide or alter native reachability; static analysis cannot resolve it.", Verdict: "uncertain"})
			continue
		}
		item.Object = nil
		candidates = append(candidates, *item)
	}
	sort.Slice(candidates, func(i, j int) bool { return candidates[i].ID < candidates[j].ID })
	sort.Slice(uncertain, func(i, j int) bool {
		return uncertain[i].File < uncertain[j].File || (uncertain[i].File == uncertain[j].File && uncertain[i].Line < uncertain[j].Line)
	})
	return candidates, uncertain, status, flags
}

func candidateID(file, name string, line int) string {
	normalized := strings.NewReplacer("/", "-", ".", "-", "_", "-").Replace(file)
	return fmt.Sprintf("%s-%s-%d", normalized, name, line)
}

func main() {
	args := parseArguments()
	root, err := filepath.Abs(args.ProjectRoot)
	if err != nil {
		fatal("cannot resolve project root: %v", err)
	}
	stats, err := os.Stat(root)
	if err != nil || !stats.IsDir() {
		fatal("project root is not a directory: %s", args.ProjectRoot)
	}
	target := absoluteWithin(root, args.Target, "target")
	targetMetas, inventory := collectTarget(root, target)
	if len(targetMetas) == 0 {
		fatal("no eligible first-party Go source under target")
	}
	allMetas := map[string]*sourceMeta{}
	for path, meta := range targetMetas {
		allMetas[path] = meta
	}
	packages, listWarning := listPackages(args.GoExecutable, root)
	exports := map[string]string{}
	for _, item := range packages {
		if item.Export != "" {
			exports[item.ImportPath] = item.Export
		}
	}
	statuses := []packageStatus{}
	candidates := []candidate{}
	uncertain := []uncertainSymbol{}
	flags := []uncertaintyFlag{}
	unavailable := []unavailableFile{}
	packageByDir := map[string]listedPackage{}
	for _, item := range packages {
		if item.Dir != "" && within(root, item.Dir) {
			packageByDir[filepath.Clean(item.Dir)] = item
		}
	}
	seenDirectories := map[string]bool{}
	for path, meta := range targetMetas {
		if !meta.Target || meta.Generated || meta.Constrained {
			if meta.Constrained {
				unavailable = append(unavailable, unavailableFile{File: meta.Relative, Reason: "build-constraint-ambiguous"})
			}
			continue
		}
		directory := filepath.Dir(path)
		if seenDirectories[directory] {
			continue
		}
		seenDirectories[directory] = true
		item, found := packageByDir[directory]
		if !found {
			statuses = append(statuses, packageStatus{Directory: relative(root, directory), Status: "package-facts-unavailable", Detail: "go list did not return an active package for this directory"})
			for _, candidateMeta := range targetMetas {
				if filepath.Dir(candidateMeta.Path) == directory && !candidateMeta.Generated && !candidateMeta.Constrained {
					unavailable = append(unavailable, unavailableFile{File: candidateMeta.Relative, Reason: "package-facts-unavailable"})
				}
			}
			continue
		}
		packageCandidates, packageUncertain, status, packageFlags := analyzePackage(root, item, targetMetas, allMetas, exports)
		statuses = append(statuses, status)
		candidates = append(candidates, packageCandidates...)
		uncertain = append(uncertain, packageUncertain...)
		flags = append(flags, packageFlags...)
		if status.Status != "complete" {
			for _, candidateMeta := range targetMetas {
				if filepath.Dir(candidateMeta.Path) == directory && !candidateMeta.Generated && !candidateMeta.Constrained {
					unavailable = append(unavailable, unavailableFile{File: candidateMeta.Relative, Reason: status.Status})
				}
			}
		}
	}
	for _, meta := range targetMetas {
		if meta.Constrained {
			continue
		}
		if meta.Generated {
			continue
		}
		if _, found := packageByDir[filepath.Dir(meta.Path)]; !found {
			continue
		}
	}
	sort.Slice(statuses, func(i, j int) bool { return statuses[i].Directory < statuses[j].Directory })
	sort.Slice(unavailable, func(i, j int) bool { return unavailable[i].File < unavailable[j].File })
	sort.Slice(candidates, func(i, j int) bool { return candidates[i].ID < candidates[j].ID })
	sort.Slice(uncertain, func(i, j int) bool {
		return uncertain[i].File < uncertain[j].File || (uncertain[i].File == uncertain[j].File && uncertain[i].Line < uncertain[j].Line)
	})
	partial := listWarning != "" || len(unavailable) > 0
	for _, status := range statuses {
		partial = partial || status.Status != "complete"
	}
	resolution := map[string]any{"state": "complete", "unavailable_files": unavailable}
	if listWarning != "" {
		resolution["go_list_warning"] = listWarning
	}
	if partial {
		resolution["state"] = "partial"
	}
	payload := output{
		SchemaVersion: 1, Language: "go", Analyzer: "go-list-go-parser-go-types", Status: "complete",
		Target: map[string]string{"path": relative(root, target)}, GoVersion: runtime.Version(), ProjectResolution: resolution,
		SourceInventory: inventory, Packages: statuses,
		Scope: map[string]string{
			"supported": "Unexported package-level Go functions and function-valued variables with zero go/types-resolved uses in the selected active-build package.",
			"excluded":  "Methods, types, safe deletion, dynamic/runtime reachability, reflection, //go:linkname, generated registration, plugin, cgo, and assembly semantics.",
		},
		Candidates: candidates, UncertainSymbols: uncertain, UncertaintyFlags: flags,
		Summary: map[string]int{"review_required": len(candidates), "uncertain": len(uncertain), "certain_delete": 0},
	}
	if partial {
		payload.Status = "partial"
	}
	if err := json.NewEncoder(os.Stdout).Encode(payload); err != nil {
		fatal("cannot encode detector result: %v", err)
	}
}
