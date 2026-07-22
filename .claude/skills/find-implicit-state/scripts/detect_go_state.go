// Detect review-worthy repeated bare-string operations on resolved Go struct fields.
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
)

type arguments struct {
	Target, ProjectRoot, Output, GoExecutable string
	GuardPackage, GuardCarrier, GuardField    string
}

type listedError struct {
	Err string `json:"Err"`
}
type listedPackage struct {
	Dir, ImportPath, Export           string
	GoFiles, InvalidGoFiles, CgoFiles []string
	Error                             *listedError
}

type inventoryRecord struct {
	RecordKind string `json:"record_kind"`
	File       string `json:"file"`
	Role       string `json:"role"`
}

type analysisRecord struct {
	RecordKind       string   `json:"record_kind"`
	Status           string   `json:"status"`
	UnavailableFiles []string `json:"unavailable_files"`
}

type operationRecord struct {
	RecordKind       string `json:"record_kind"`
	Classification   string `json:"classification"`
	File             string `json:"file"`
	Line             int    `json:"line"`
	Operation        string `json:"operation"`
	Literal          string `json:"literal"`
	Field            string `json:"field"`
	CarrierType      string `json:"carrier_type"`
	FieldType        string `json:"field_type"`
	PackagePath      string `json:"package_path"`
	EvidenceStrength string `json:"evidence_strength"`
	fieldID          string
	fieldNamed       bool
}

var skippedDirectories = map[string]bool{
	".git": true, ".venv": true, "build": true, "dist": true,
	"node_modules": true, "reports": true, "vendor": true,
}

func fatal(format string, values ...any) {
	fmt.Fprintf(os.Stderr, "[detect_go_state] %s\n", fmt.Sprintf(format, values...))
	os.Exit(2)
}

func parseArguments() arguments {
	values := arguments{}
	flag.StringVar(&values.Target, "target", "", "Go file or directory target")
	flag.StringVar(&values.ProjectRoot, "project-root", "", "host project root")
	flag.StringVar(&values.Output, "output", "", "JSONL output beneath reports/implicit-state")
	flag.StringVar(&values.GoExecutable, "go-executable", "go", "Go executable")
	flag.StringVar(&values.GuardPackage, "guard-package", "", "exact package path for guard mode")
	flag.StringVar(&values.GuardCarrier, "guard-carrier", "", "exact carrier type for guard mode")
	flag.StringVar(&values.GuardField, "guard-field", "", "exact field for guard mode")
	flag.Parse()
	if values.Target == "" || values.ProjectRoot == "" || values.Output == "" || flag.NArg() != 0 {
		fatal("usage: detect_go_state.go --target <path> --project-root <path> --output <jsonl>")
	}
	return values
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

func parseFile(root, path string) *ast.File {
	parsed, err := parser.ParseFile(token.NewFileSet(), path, nil, parser.ParseComments|parser.AllErrors|parser.SkipObjectResolution)
	if err != nil {
		fatal("syntax-error in %s: %v", relative(root, path), err)
	}
	return parsed
}

func inventory(root, target string) ([]inventoryRecord, map[string]bool) {
	selected := map[string]bool{}
	records := []inventoryRecord{}
	add := func(path string) {
		if strings.ToLower(filepath.Ext(path)) != ".go" {
			return
		}
		parsed := parseFile(root, path)
		role := "first_party"
		name := strings.ToLower(filepath.Base(path))
		if strings.HasSuffix(name, "_test.go") {
			role = "excluded_test"
		}
		if ast.IsGenerated(parsed) {
			role = "excluded_generated"
		}
		records = append(records, inventoryRecord{RecordKind: "source_inventory", File: relative(root, path), Role: role})
		if role == "first_party" {
			selected[filepath.Clean(path)] = true
		}
	}
	info, err := os.Lstat(target)
	if err != nil {
		fatal("target does not exist: %v", err)
	}
	if info.Mode()&os.ModeSymlink != 0 {
		fatal("target must not be a symbolic link")
	}
	if info.Mode().IsRegular() {
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
				return fmt.Errorf("symbolic link in target: %s", relative(root, path))
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
			fatal("cannot inventory target: %v", err)
		}
	} else {
		fatal("target must be a .go file or directory")
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
			fatal("go list emitted malformed package JSON")
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
		fatal("type facts unavailable: %s", detail)
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

func unquote(literal *ast.BasicLit) (string, bool) {
	if literal == nil || literal.Kind != token.STRING {
		return "", false
	}
	value, err := strconv.Unquote(literal.Value)
	return value, err == nil
}

func unwrap(expression ast.Expr) ast.Expr {
	for {
		parenthesized, ok := expression.(*ast.ParenExpr)
		if !ok {
			return expression
		}
		expression = parenthesized.X
	}
}

func carrierName(value types.Type) string {
	for {
		pointer, ok := value.(*types.Pointer)
		if !ok {
			break
		}
		value = pointer.Elem()
	}
	if named, ok := value.(*types.Named); ok && named.Obj() != nil {
		return named.Obj().Name()
	}
	return types.TypeString(value, func(*types.Package) string { return "" })
}

func fieldType(value types.Type) (string, bool, bool) {
	if named, ok := value.(*types.Named); ok {
		basic, isBasic := named.Underlying().(*types.Basic)
		return named.Obj().Name(), true, isBasic && basic.Kind() == types.String
	}
	basic, ok := value.(*types.Basic)
	return types.TypeString(value, func(*types.Package) string { return "" }), false, ok && basic.Kind() == types.String
}

func selectorFact(info *types.Info, expression ast.Expr) (string, string, string, bool, string, bool) {
	selector, ok := unwrap(expression).(*ast.SelectorExpr)
	if !ok {
		return "", "", "", false, "", false
	}
	selection := info.Selections[selector]
	if selection == nil || selection.Kind() != types.FieldVal {
		return "", "", "", false, "", false
	}
	field, ok := selection.Obj().(*types.Var)
	if !ok {
		return "", "", "", false, "", false
	}
	typeName, named, stringLike := fieldType(field.Type())
	if !stringLike {
		return "", "", "", false, "", false
	}
	carrier := carrierName(selection.Recv())
	identifier := field.Pkg().Path() + ":" + carrier + "." + field.Name()
	return field.Name(), carrier, typeName, named, identifier, true
}

func stateLike(name string) bool {
	switch strings.ToLower(name) {
	case "state", "status", "phase":
		return true
	}
	return false
}

func vendorCarrier(name string) bool {
	lower := strings.ToLower(name)
	if strings.HasPrefix(lower, "vendor") {
		return true
	}
	for _, suffix := range []string{"payload", "request", "response", "event", "message", "wire"} {
		if strings.HasSuffix(lower, suffix) {
			return true
		}
	}
	return false
}

func analyzePackage(root string, item listedPackage, selected map[string]bool, exports map[string]string) []operationRecord {
	if !within(root, item.Dir) {
		return nil
	}
	packageSelected := false
	for _, name := range append(append([]string{}, item.GoFiles...), item.InvalidGoFiles...) {
		if selected[filepath.Clean(filepath.Join(item.Dir, name))] {
			packageSelected = true
			break
		}
	}
	if !packageSelected {
		return nil
	}
	if item.Error != nil && item.Error.Err != "" {
		fatal("type facts unavailable for %s: %s", relative(root, item.Dir), item.Error.Err)
	}
	if len(item.CgoFiles) > 0 {
		fatal("type facts unavailable for %s: cgo is outside the Go v1 state model", relative(root, item.Dir))
	}
	fset := token.NewFileSet()
	files := []*ast.File{}
	paths := map[*ast.File]string{}
	for _, name := range append(append([]string{}, item.GoFiles...), item.InvalidGoFiles...) {
		path := filepath.Clean(filepath.Join(item.Dir, name))
		parsed, err := parser.ParseFile(fset, path, nil, parser.ParseComments|parser.AllErrors|parser.SkipObjectResolution)
		if err != nil {
			fatal("syntax-error in %s: %v", relative(root, path), err)
		}
		files, paths[parsed] = append(files, parsed), path
	}
	if len(files) == 0 {
		return nil
	}
	info := types.Info{Types: map[ast.Expr]types.TypeAndValue{}, Defs: map[*ast.Ident]types.Object{}, Uses: map[*ast.Ident]types.Object{}, Selections: map[*ast.SelectorExpr]*types.Selection{}}
	config := types.Config{Importer: exportImporter(fset, exports)}
	if _, err := config.Check(item.ImportPath, fset, files, &info); err != nil {
		fatal("type facts unavailable for %s: %v", relative(root, item.Dir), err)
	}
	result := []operationRecord{}
	add := func(file *ast.File, pos token.Pos, operation, literal string, expression ast.Expr) {
		field, carrier, typeName, named, identifier, ok := selectorFact(&info, expression)
		if !ok {
			return
		}
		result = append(result, operationRecord{RecordKind: "operation", File: relative(root, paths[file]), Line: fset.PositionFor(pos, true).Line, Operation: operation, Literal: literal, Field: field, CarrierType: carrier, FieldType: typeName, PackagePath: item.ImportPath, fieldID: identifier, fieldNamed: named})
	}
	for _, file := range files {
		if !selected[filepath.Clean(paths[file])] {
			continue
		}
		ast.Inspect(file, func(node ast.Node) bool {
			switch typed := node.(type) {
			case *ast.BinaryExpr:
				if typed.Op != token.EQL && typed.Op != token.NEQ {
					return true
				}
				if literalNode, ok := unwrap(typed.Y).(*ast.BasicLit); ok {
					if literal, ok := unquote(literalNode); ok {
						add(file, typed.Pos(), "comparison", literal, typed.X)
					}
				}
				if literalNode, ok := unwrap(typed.X).(*ast.BasicLit); ok {
					if literal, ok := unquote(literalNode); ok {
						add(file, typed.Pos(), "comparison", literal, typed.Y)
					}
				}
			case *ast.AssignStmt:
				if typed.Tok != token.ASSIGN || len(typed.Lhs) != len(typed.Rhs) {
					return true
				}
				for index, left := range typed.Lhs {
					literalNode, ok := unwrap(typed.Rhs[index]).(*ast.BasicLit)
					if !ok {
						continue
					}
					if literal, ok := unquote(literalNode); ok {
						add(file, left.Pos(), "assignment", literal, left)
					}
				}
			}
			return true
		})
	}
	return result
}

func classify(records []operationRecord, args arguments) {
	counts := map[string]int{}
	literals := map[string]map[string]bool{}
	for _, record := range records {
		counts[record.fieldID]++
		if literals[record.fieldID] == nil {
			literals[record.fieldID] = map[string]bool{}
		}
		literals[record.fieldID][record.Literal] = true
	}
	for index := range records {
		record := &records[index]
		switch {
		case args.GuardPackage != "" && record.PackagePath == args.GuardPackage && record.CarrierType == args.GuardCarrier && record.Field == args.GuardField:
			record.Classification, record.EvidenceStrength = "guard_violation", "accepted_invariant"
		case args.GuardPackage != "":
			record.Classification, record.EvidenceStrength = "outside_guard_scope", "excluded"
		case !stateLike(record.Field):
			record.Classification, record.EvidenceStrength = "unrelated_string_field", "excluded"
		case vendorCarrier(record.CarrierType):
			record.Classification, record.EvidenceStrength = "possible_vendor_boundary", "naming_convention_candidate"
		case record.fieldNamed:
			record.Classification, record.EvidenceStrength = "typed_state_authority", "existing_authority"
		case counts[record.fieldID] >= 3 && len(literals[record.fieldID]) >= 2:
			record.Classification, record.EvidenceStrength = "first_party_state_operation", "review_candidate"
		default:
			record.Classification, record.EvidenceStrength = "insufficient_closed_state_evidence", "insufficient"
		}
	}
}

func writeJSONL(path string, inventory []inventoryRecord, status analysisRecord, operations []operationRecord) {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		fatal("cannot create output directory: %v", err)
	}
	temporary := fmt.Sprintf("%s.tmp-%d", path, os.Getpid())
	file, err := os.Create(temporary)
	if err != nil {
		fatal("cannot stage output: %v", err)
	}
	encoder := json.NewEncoder(file)
	for _, record := range inventory {
		if err := encoder.Encode(record); err != nil {
			fatal("cannot write output: %v", err)
		}
	}
	if err := encoder.Encode(status); err != nil {
		fatal("cannot write output: %v", err)
	}
	for _, record := range operations {
		if err := encoder.Encode(record); err != nil {
			fatal("cannot write output: %v", err)
		}
	}
	if err := file.Close(); err != nil {
		fatal("cannot close output: %v", err)
	}
	if err := os.Rename(temporary, path); err != nil {
		fatal("cannot publish output: %v", err)
	}
}

func main() {
	args := parseArguments()
	root, err := filepath.Abs(args.ProjectRoot)
	if err != nil {
		fatal("cannot resolve project root: %v", err)
	}
	target, err := filepath.Abs(args.Target)
	if err != nil || !within(root, target) {
		fatal("target must stay inside project root")
	}
	output, err := filepath.Abs(args.Output)
	if err != nil || !within(filepath.Join(root, "reports", "implicit-state"), output) {
		fatal("output must stay beneath reports/implicit-state")
	}
	inventoryRecords, selected := inventory(root, target)
	if len(selected) == 0 {
		fatal("no eligible first-party Go source under target")
	}
	packages, exports := listPackages(args.GoExecutable, root)
	active := map[string]bool{}
	for _, item := range packages {
		if !within(root, item.Dir) {
			continue
		}
		for _, name := range append(append([]string{}, item.GoFiles...), item.InvalidGoFiles...) {
			active[filepath.Clean(filepath.Join(item.Dir, name))] = true
		}
	}
	unavailable := []string{}
	for index := range inventoryRecords {
		path := filepath.Clean(filepath.Join(root, filepath.FromSlash(inventoryRecords[index].File)))
		if inventoryRecords[index].Role == "first_party" && !active[path] {
			inventoryRecords[index].Role = "inactive_build"
			delete(selected, path)
			unavailable = append(unavailable, inventoryRecords[index].File)
		}
	}
	sort.Strings(unavailable)
	operations := []operationRecord{}
	for _, item := range packages {
		operations = append(operations, analyzePackage(root, item, selected, exports)...)
	}
	guardFields := 0
	for _, value := range []string{args.GuardPackage, args.GuardCarrier, args.GuardField} {
		if value != "" {
			guardFields++
		}
	}
	if guardFields != 0 && guardFields != 3 {
		fatal("guard mode requires --guard-package, --guard-carrier, and --guard-field together")
	}
	classify(operations, args)
	sort.Slice(operations, func(i, j int) bool {
		return operations[i].File < operations[j].File || (operations[i].File == operations[j].File && operations[i].Line < operations[j].Line)
	})
	status := analysisRecord{RecordKind: "analysis_status", Status: "complete", UnavailableFiles: unavailable}
	if len(unavailable) > 0 {
		status.Status = "partial"
	}
	writeJSONL(output, inventoryRecords, status, operations)
}
