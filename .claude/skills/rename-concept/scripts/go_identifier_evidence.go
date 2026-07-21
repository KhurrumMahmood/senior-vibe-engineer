// Classify Go rename identifiers using project-local go/types facts.
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
	"strings"
	"unicode"
)

type arguments struct {
	ProjectRoot, OldTerms, NewTerms, Sources, Output, GoExecutable string
}

type listedError struct {
	Err string `json:"Err"`
}

type listedPackage struct {
	Dir, ImportPath, Name, Export     string
	GoFiles, CgoFiles, InvalidGoFiles []string
	Error                             *listedError
}

type declaration struct {
	File string `json:"file"`
	Line int    `json:"line"`
	Name string `json:"name"`
	Kind string `json:"kind"`
}

type occurrence struct {
	File           string `json:"file"`
	Line           int    `json:"line"`
	Name           string `json:"name"`
	Classification string `json:"classification"`
}

type evidence struct {
	Status                string                   `json:"status"`
	GoVersion             string                   `json:"go_version"`
	Declarations          map[string][]declaration `json:"declarations"`
	Occurrences           []occurrence             `json:"occurrences"`
	ResolutionDiagnostics []string                 `json:"resolution_diagnostics"`
	UncoveredFiles        []string                 `json:"uncovered_files"`
}

func fatal(format string, values ...any) {
	fmt.Fprintf(os.Stderr, "[go_identifier_evidence] %s\n", fmt.Sprintf(format, values...))
	os.Exit(2)
}

func parseArguments() arguments {
	values := arguments{}
	flag.StringVar(&values.ProjectRoot, "project-root", "", "host project root")
	flag.StringVar(&values.OldTerms, "old-terms", "", "JSON array of deprecated terms")
	flag.StringVar(&values.NewTerms, "new-terms", "", "JSON array of canonical terms")
	flag.StringVar(&values.Sources, "sources", "", "JSON array of selected Go sources")
	flag.StringVar(&values.Output, "output", "", "temporary evidence JSON")
	flag.StringVar(&values.GoExecutable, "go-executable", "go", "Go executable")
	flag.Parse()
	if values.ProjectRoot == "" || values.OldTerms == "" || values.NewTerms == "" || values.Sources == "" || values.Output == "" || flag.NArg() != 0 {
		fatal("usage: go_identifier_evidence.go --project-root <path> --old-terms <json> --new-terms <json> --sources <json> --output <path>")
	}
	return values
}

func decodeStrings(raw, label string) []string {
	values := []string{}
	if err := json.Unmarshal([]byte(raw), &values); err != nil || len(values) == 0 {
		fatal("%s must be a non-empty JSON string array", label)
	}
	return values
}

func normalize(value string) string {
	var output strings.Builder
	for _, char := range value {
		if unicode.IsLetter(char) || unicode.IsDigit(char) {
			output.WriteRune(unicode.ToLower(char))
		}
	}
	return output.String()
}

func termSet(values []string) map[string]bool {
	result := map[string]bool{}
	for _, value := range values {
		if normalized := normalize(value); normalized != "" {
			result[normalized] = true
		}
	}
	return result
}

func within(root, candidate string) bool {
	relative, err := filepath.Rel(root, candidate)
	return err == nil && (relative == "." || (relative != ".." && !strings.HasPrefix(relative, ".."+string(os.PathSeparator)) && !filepath.IsAbs(relative)))
}

func relative(root, path string) string {
	value, err := filepath.Rel(root, path)
	if err != nil {
		return filepath.ToSlash(path)
	}
	return filepath.ToSlash(value)
}

func selectedSources(root string, supplied []string) map[string]bool {
	selected := map[string]bool{}
	for _, value := range supplied {
		path := value
		if !filepath.IsAbs(path) {
			path = filepath.Join(root, path)
		}
		path = filepath.Clean(path)
		if !within(root, path) || strings.ToLower(filepath.Ext(path)) != ".go" {
			fatal("source must be a project-relative .go file: %s", value)
		}
		info, err := os.Lstat(path)
		if err != nil || !info.Mode().IsRegular() || info.Mode()&os.ModeSymlink != 0 {
			fatal("source must be a regular non-symlink file: %s", value)
		}
		selected[path] = true
	}
	return selected
}

func listPackages(goExecutable, root string) ([]listedPackage, map[string]string) {
	command := exec.Command(goExecutable, "list", "-deps", "-export", "-json", "-e", "./...")
	command.Dir = root
	var stdout bytes.Buffer
	command.Stdout = &stdout
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
			fatal("go list emitted malformed package JSON")
		}
		packages = append(packages, item)
		if item.Export != "" {
			exports[item.ImportPath] = item.Export
		}
	}
	if len(packages) == 0 {
		fatal("go list returned no package facts")
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

func objectKind(object types.Object) string {
	switch object.(type) {
	case *types.TypeName:
		return "type"
	case *types.Const:
		return "const"
	case *types.Var:
		return "variable"
	case *types.Func:
		return "function"
	default:
		return "symbol"
	}
}

func objectKey(object types.Object) string {
	if object == nil || object.Pkg() == nil {
		return ""
	}
	return object.Pkg().Path() + ":" + object.Name()
}

func classify(object types.Object, definitions bool, authority map[string]string, current *types.Package) string {
	if class := authority[objectKey(object)]; class != "" {
		return class + "_concept_symbol"
	}
	if object == nil {
		return "unresolved_identifier"
	}
	switch value := object.(type) {
	case *types.PkgName:
		return "import_alias"
	case *types.Var:
		if value.IsField() {
			return "property_key"
		}
	}
	if object.Pkg() != nil && object.Pkg() != current {
		return "external_symbol"
	}
	if definitions && object.Parent() == current.Scope() {
		return "unexported_declaration"
	}
	return "shadowed_local"
}

func authorityKeys(packages []listedPackage, selected map[string]bool, oldTerms, newTerms map[string]bool) map[string]string {
	authority := map[string]string{}
	for _, item := range packages {
		for _, name := range append(append([]string{}, item.GoFiles...), item.CgoFiles...) {
			path := filepath.Clean(filepath.Join(item.Dir, name))
			if !selected[path] {
				continue
			}
			parsed, err := parser.ParseFile(token.NewFileSet(), path, nil, parser.SkipObjectResolution)
			if err != nil {
				continue
			}
			add := func(name string) {
				if !ast.IsExported(name) {
					return
				}
				normalized := normalize(name)
				if oldTerms[normalized] {
					authority[item.ImportPath+":"+name] = "old"
				} else if newTerms[normalized] {
					authority[item.ImportPath+":"+name] = "new"
				}
			}
			for _, raw := range parsed.Decls {
				switch declaration := raw.(type) {
				case *ast.FuncDecl:
					if declaration.Recv == nil {
						add(declaration.Name.Name)
					}
				case *ast.GenDecl:
					for _, rawSpec := range declaration.Specs {
						switch spec := rawSpec.(type) {
						case *ast.TypeSpec:
							add(spec.Name.Name)
						case *ast.ValueSpec:
							for _, identifier := range spec.Names {
								add(identifier.Name)
							}
						}
					}
				}
			}
		}
	}
	return authority
}

func main() {
	args := parseArguments()
	root, err := filepath.Abs(args.ProjectRoot)
	if err != nil {
		fatal("invalid project root: %v", err)
	}
	oldTerms := termSet(decodeStrings(args.OldTerms, "old terms"))
	newTerms := termSet(decodeStrings(args.NewTerms, "new terms"))
	selected := selectedSources(root, decodeStrings(args.Sources, "sources"))
	versionCommand := exec.Command(args.GoExecutable, "version")
	versionCommand.Dir = root
	versionBytes, err := versionCommand.CombinedOutput()
	if err != nil {
		fatal("cannot determine Go version: %v", err)
	}
	packages, exports := listPackages(args.GoExecutable, root)
	authority := authorityKeys(packages, selected, oldTerms, newTerms)
	result := evidence{
		Status: "resolved", GoVersion: strings.TrimSpace(string(versionBytes)),
		Declarations: map[string][]declaration{"old": {}, "new": {}},
		Occurrences:  []occurrence{}, ResolutionDiagnostics: []string{}, UncoveredFiles: []string{},
	}
	active := map[string]bool{}
	for _, item := range packages {
		if item.Dir == "" || !within(root, item.Dir) {
			continue
		}
		paths := []string{}
		hasSelected := false
		for _, name := range append(append([]string{}, item.GoFiles...), item.CgoFiles...) {
			path := filepath.Clean(filepath.Join(item.Dir, name))
			paths = append(paths, path)
			if selected[path] {
				active[path] = true
				hasSelected = true
			}
		}
		if len(paths) == 0 || !hasSelected {
			continue
		}
		if item.Error != nil || len(item.InvalidGoFiles) > 0 {
			result.Status = "partial"
			if item.Error != nil {
				result.ResolutionDiagnostics = append(result.ResolutionDiagnostics, item.ImportPath+": "+item.Error.Err)
			}
			continue
		}
		fset := token.NewFileSet()
		files := []*ast.File{}
		parseFailed := false
		for _, path := range paths {
			parsed, parseErr := parser.ParseFile(fset, path, nil, parser.ParseComments|parser.AllErrors)
			if parseErr != nil {
				result.Status = "partial"
				result.ResolutionDiagnostics = append(result.ResolutionDiagnostics, relative(root, path)+": "+parseErr.Error())
				parseFailed = true
				break
			}
			files = append(files, parsed)
		}
		if parseFailed {
			continue
		}
		info := &types.Info{
			Types: map[ast.Expr]types.TypeAndValue{}, Defs: map[*ast.Ident]types.Object{},
			Uses: map[*ast.Ident]types.Object{}, Selections: map[*ast.SelectorExpr]*types.Selection{},
		}
		typeErrors := []string{}
		config := &types.Config{
			Importer: exportImporter(fset, exports), FakeImportC: true,
			Error: func(err error) { typeErrors = append(typeErrors, err.Error()) },
		}
		checked, _ := config.Check(item.ImportPath, fset, files, info)
		if checked == nil || len(typeErrors) > 0 {
			result.Status = "partial"
			result.ResolutionDiagnostics = append(result.ResolutionDiagnostics, typeErrors...)
			continue
		}
		for fileIndex, file := range files {
			if !selected[paths[fileIndex]] {
				continue
			}
			for identifier, object := range info.Defs {
				if object == nil || object.Parent() != checked.Scope() || !object.Exported() {
					continue
				}
				normalized := normalize(identifier.Name)
				class := ""
				if oldTerms[normalized] {
					class = "old"
				} else if newTerms[normalized] {
					class = "new"
				}
				if class == "" {
					continue
				}
				if authority[objectKey(object)] != class {
					continue
				}
				result.Declarations[class] = append(result.Declarations[class], declaration{
					File: relative(root, paths[fileIndex]), Line: fset.Position(identifier.Pos()).Line,
					Name: identifier.Name, Kind: objectKind(object),
				})
			}
			_ = file
		}
		for fileIndex, file := range files {
			path := paths[fileIndex]
			if !selected[path] {
				continue
			}
			ast.Inspect(file, func(node ast.Node) bool {
				identifier, ok := node.(*ast.Ident)
				if !ok {
					return true
				}
				normalized := normalize(identifier.Name)
				if !oldTerms[normalized] && !newTerms[normalized] {
					return true
				}
				object := info.Defs[identifier]
				isDefinition := object != nil
				if object == nil {
					object = info.Uses[identifier]
				}
				result.Occurrences = append(result.Occurrences, occurrence{
					File: relative(root, path), Line: fset.Position(identifier.Pos()).Line,
					Name: identifier.Name, Classification: classify(object, isDefinition, authority, checked),
				})
				return true
			})
		}
	}
	for path := range selected {
		if !active[path] {
			result.UncoveredFiles = append(result.UncoveredFiles, relative(root, path))
		}
	}
	if len(result.UncoveredFiles) > 0 {
		result.Status = "partial"
	}
	for _, class := range []string{"old", "new"} {
		sort.Slice(result.Declarations[class], func(i, j int) bool {
			left, right := result.Declarations[class][i], result.Declarations[class][j]
			return left.File < right.File || (left.File == right.File && left.Line < right.Line)
		})
	}
	sort.Slice(result.Occurrences, func(i, j int) bool {
		left, right := result.Occurrences[i], result.Occurrences[j]
		return left.File < right.File || (left.File == right.File && (left.Line < right.Line || (left.Line == right.Line && left.Name < right.Name)))
	})
	sort.Strings(result.ResolutionDiagnostics)
	sort.Strings(result.UncoveredFiles)
	content, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		fatal("cannot encode evidence: %v", err)
	}
	if err := os.WriteFile(args.Output, append(content, '\n'), 0o644); err != nil {
		fatal("cannot write evidence: %v", err)
	}
}
