// Produce conservative Go function-level semantic-duplication review leads.
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
	"go/scanner"
	"go/token"
	"go/types"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
)

type arguments struct {
	Target, ProjectRoot, ReportDir, GoExecutable string
}

type listedError struct {
	Err string `json:"Err"`
}

type listedPackage struct {
	Dir, ImportPath, Name, Export                     string
	GoFiles, CgoFiles, IgnoredGoFiles, InvalidGoFiles []string
	Error                                             *listedError
}

type inventoryRecord struct {
	File string `json:"file"`
	Role string `json:"role"`
}

type memberRecord struct {
	File          string `json:"file"`
	QualifiedName string `json:"qualified_name"`
	Line          int    `json:"line"`
	EndLine       int    `json:"end_line"`
	Size          int    `json:"size"`
	CallerCount   int    `json:"caller_count"`
}

type findingRecord struct {
	Level                  string              `json:"level"`
	Members                []memberRecord      `json:"members"`
	StaticReturnType       string              `json:"static_return_type"`
	ReturnFields           []string            `json:"return_fields"`
	Similarity             float64             `json:"similarity"`
	FindingID              string              `json:"finding_id,omitempty"`
	ID                     string              `json:"id,omitempty"`
	InvestigationStatus    string              `json:"investigation_status"`
	ReasonCode             *string             `json:"reason_code"`
	SharedCoreDescription  string              `json:"shared_core_description,omitempty"`
	Divergence             map[string][]string `json:"divergence,omitempty"`
	ConsolidationShape     string              `json:"consolidation_shape,omitempty"`
	MaintenanceRiskDomain  string              `json:"maintenance_risk_domain,omitempty"`
	MatrixPath             string              `json:"matrix_path,omitempty"`
	TestsThatGuardThisArea []string            `json:"tests_that_guard_this_area,omitempty"`
	Notes                  string              `json:"notes"`
}

type candidate struct {
	File, Name, Key, ReturnTypeText string
	Line, EndLine                   int
	Fields                          []string
	Tokens                          map[string]bool
	Policy                          []string
	Concerns                        []string
	Calls                           map[*types.Func]bool
	Object                          *types.Func
	ReturnType                      types.Type
}

var skippedDirectories = map[string]bool{
	".git": true, ".venv": true, "build": true, "dist": true,
	"node_modules": true, "reports": true, "vendor": true,
	"test": true, "tests": true, "fixtures": true, "generated": true,
}

func fatal(format string, values ...any) {
	fmt.Fprintf(os.Stderr, "[detect_go_semantic] %s\n", fmt.Sprintf(format, values...))
	os.Exit(2)
}

func parseArguments() arguments {
	values := arguments{}
	flag.StringVar(&values.Target, "target", "", "Go file or directory target")
	flag.StringVar(&values.ProjectRoot, "project-root", "", "host project root")
	flag.StringVar(&values.ReportDir, "report-dir", "", "staged report directory")
	flag.StringVar(&values.GoExecutable, "go-executable", "go", "Go executable")
	flag.Parse()
	if values.Target == "" || values.ProjectRoot == "" || values.ReportDir == "" || flag.NArg() != 0 {
		fatal("usage: detect_go_semantic.go --target <path> --project-root <path> --report-dir <path>")
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

func inventory(root, target string) ([]inventoryRecord, map[string]bool) {
	records := []inventoryRecord{}
	selected := map[string]bool{}
	add := func(path string) {
		if strings.ToLower(filepath.Ext(path)) != ".go" {
			return
		}
		fset := token.NewFileSet()
		parsed, err := parser.ParseFile(fset, path, nil, parser.ParseComments|parser.AllErrors|parser.SkipObjectResolution)
		if err != nil {
			fatal("syntax-error in %s: %v", relative(root, path), err)
		}
		role := "first_party"
		name := strings.ToLower(filepath.Base(path))
		if strings.HasSuffix(name, "_test.go") {
			role = "excluded_test"
		}
		if ast.IsGenerated(parsed) {
			role = "excluded_generated"
		}
		records = append(records, inventoryRecord{File: relative(root, path), Role: role})
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

func namedStruct(value types.Type) (*types.Named, *types.Struct, bool) {
	if pointer, ok := value.(*types.Pointer); ok {
		value = pointer.Elem()
	}
	named, ok := value.(*types.Named)
	if !ok {
		return nil, nil, false
	}
	structure, ok := named.Underlying().(*types.Struct)
	return named, structure, ok
}

func equalStrings(left, right []string) bool {
	if len(left) != len(right) {
		return false
	}
	for index := range left {
		if left[index] != right[index] {
			return false
		}
	}
	return true
}

func returnedFields(function *ast.FuncDecl, info *types.Info, resultType types.Type) ([]string, bool) {
	_, structure, ok := namedStruct(resultType)
	if !ok || structure.NumFields() < 2 {
		return nil, false
	}
	var expected []string
	valid := true
	returns := 0
	ast.Inspect(function.Body, func(node ast.Node) bool {
		if !valid {
			return false
		}
		if _, nested := node.(*ast.FuncLit); nested {
			return false
		}
		statement, isReturn := node.(*ast.ReturnStmt)
		if !isReturn {
			return true
		}
		returns++
		if len(statement.Results) != 1 {
			valid = false
			return false
		}
		literal := unwrapComposite(statement.Results[0])
		literalType := types.Type(nil)
		if literal != nil {
			literalType = info.TypeOf(literal)
		}
		matchesResult := literalType != nil && types.Identical(literalType, resultType)
		if pointer, ok := resultType.(*types.Pointer); ok && literalType != nil {
			matchesResult = matchesResult || types.Identical(literalType, pointer.Elem())
		}
		if literal == nil || !matchesResult {
			valid = false
			return false
		}
		fields := []string{}
		keyed := false
		for _, element := range literal.Elts {
			pair, isPair := element.(*ast.KeyValueExpr)
			if !isPair {
				continue
			}
			identifier, isIdentifier := pair.Key.(*ast.Ident)
			if !isIdentifier {
				valid = false
				return false
			}
			keyed = true
			fields = append(fields, identifier.Name)
		}
		if !keyed {
			for index := 0; index < structure.NumFields(); index++ {
				fields = append(fields, structure.Field(index).Name())
			}
		}
		sort.Strings(fields)
		if len(fields) < 2 || (expected != nil && !equalStrings(expected, fields)) {
			valid = false
			return false
		}
		expected = fields
		return false
	})
	return expected, valid && returns > 0
}

func bodyTokens(fset *token.FileSet, file *ast.File, function *ast.FuncDecl) map[string]bool {
	position := fset.Position(function.Body.Pos())
	end := fset.Position(function.Body.End())
	source, err := os.ReadFile(position.Filename)
	if err != nil || position.Offset < 0 || end.Offset > len(source) || position.Offset >= end.Offset {
		return map[string]bool{}
	}
	content := source[position.Offset:end.Offset]
	localSet := token.NewFileSet()
	localFile := localSet.AddFile("body.go", localSet.Base(), len(content))
	var lexer scanner.Scanner
	lexer.Init(localFile, content, nil, scanner.ScanComments)
	tokens := map[string]bool{}
	for {
		_, kind, literal := lexer.Scan()
		if kind == token.EOF {
			break
		}
		value := kind.String()
		if literal != "" && kind != token.COMMENT {
			value = literal
		}
		if kind != token.SEMICOLON && kind != token.COMMENT {
			tokens[value] = true
		}
	}
	return tokens
}

func callFacts(function *ast.FuncDecl, info *types.Info) (map[*types.Func]bool, []string, []string) {
	calls := map[*types.Func]bool{}
	concerns := map[string]bool{}
	policy := map[string]bool{}
	ast.Inspect(function.Body, func(node ast.Node) bool {
		if _, nested := node.(*ast.FuncLit); nested {
			return false
		}
		switch value := node.(type) {
		case *ast.DeferStmt:
			policy["defer"] = true
		case *ast.GoStmt:
			policy["goroutine"] = true
		case *ast.CallExpr:
			var object types.Object
			switch target := value.Fun.(type) {
			case *ast.Ident:
				object = info.Uses[target]
				if builtin, ok := object.(*types.Builtin); ok {
					if builtin.Name() == "panic" || builtin.Name() == "recover" {
						policy[builtin.Name()] = true
					}
					return true
				}
			case *ast.SelectorExpr:
				object = info.Uses[target.Sel]
			}
			if functionObject, ok := object.(*types.Func); ok {
				calls[functionObject] = true
				return true
			}
			callType := info.TypeOf(value.Fun)
			if callType != nil {
				if signature, ok := callType.Underlying().(*types.Signature); ok && signature != nil {
					concerns["dynamic_function_call"] = true
				}
			}
		}
		return true
	})
	concernList := make([]string, 0, len(concerns))
	for value := range concerns {
		concernList = append(concernList, value)
	}
	policyList := make([]string, 0, len(policy))
	for value := range policy {
		policyList = append(policyList, value)
	}
	sort.Strings(concernList)
	sort.Strings(policyList)
	return calls, concernList, policyList
}

func lexicalSimilarity(left, right map[string]bool) float64 {
	if len(left) == 0 && len(right) == 0 {
		return 1
	}
	intersection := 0
	union := map[string]bool{}
	for value := range left {
		union[value] = true
		if right[value] {
			intersection++
		}
	}
	for value := range right {
		union[value] = true
	}
	return float64(intersection) / float64(len(union))
}

func collectCandidates(root string, packages []listedPackage, exports map[string]string, selected map[string]bool) ([]*candidate, map[*types.Func]int, map[string]bool) {
	all := []*candidate{}
	incoming := map[*types.Func]int{}
	active := map[string]bool{}
	for _, item := range packages {
		if item.Dir == "" || !within(root, item.Dir) {
			continue
		}
		if item.Error != nil || len(item.InvalidGoFiles) > 0 {
			detail := "invalid package"
			if item.Error != nil {
				detail = item.Error.Err
			}
			fatal("type facts unavailable for %s: %s", item.ImportPath, detail)
		}
		paths := []string{}
		for _, name := range append(append([]string{}, item.GoFiles...), item.CgoFiles...) {
			path := filepath.Clean(filepath.Join(item.Dir, name))
			paths = append(paths, path)
			active[path] = true
		}
		if len(paths) == 0 {
			continue
		}
		fset := token.NewFileSet()
		files := []*ast.File{}
		for _, path := range paths {
			parsed, err := parser.ParseFile(fset, path, nil, parser.ParseComments|parser.AllErrors)
			if err != nil {
				fatal("syntax-error in %s: %v", relative(root, path), err)
			}
			files = append(files, parsed)
		}
		info := &types.Info{
			Types:      map[ast.Expr]types.TypeAndValue{},
			Defs:       map[*ast.Ident]types.Object{},
			Uses:       map[*ast.Ident]types.Object{},
			Selections: map[*ast.SelectorExpr]*types.Selection{},
		}
		typeErrors := []string{}
		config := &types.Config{
			Importer:    exportImporter(fset, exports),
			FakeImportC: true,
			Error: func(err error) {
				typeErrors = append(typeErrors, err.Error())
			},
		}
		checked, _ := config.Check(item.ImportPath, fset, files, info)
		if checked == nil || len(typeErrors) > 0 {
			fatal("type facts unavailable for %s: %s", item.ImportPath, strings.Join(typeErrors, "; "))
		}
		for fileIndex, file := range files {
			path := paths[fileIndex]
			for _, declaration := range file.Decls {
				function, ok := declaration.(*ast.FuncDecl)
				if !ok || function.Recv != nil || function.Body == nil {
					continue
				}
				object, ok := info.Defs[function.Name].(*types.Func)
				if !ok {
					continue
				}
				calls, _, _ := callFacts(function, info)
				for called := range calls {
					incoming[called]++
				}
				if !selected[path] || strings.HasPrefix(strings.ToLower(function.Name.Name), "mock") || strings.HasPrefix(strings.ToLower(function.Name.Name), "fake") || strings.HasPrefix(strings.ToLower(function.Name.Name), "stub") {
					continue
				}
				signature, ok := object.Type().(*types.Signature)
				if !ok || signature.Results().Len() != 1 {
					continue
				}
				resultType := signature.Results().At(0).Type()
				fields, ok := returnedFields(function, info, resultType)
				if !ok {
					continue
				}
				calls, concerns, policy := callFacts(function, info)
				start := fset.Position(function.Pos()).Line
				end := fset.Position(function.End()).Line
				all = append(all, &candidate{
					File: relative(root, path), Name: function.Name.Name,
					Key:            item.ImportPath + "." + function.Name.Name,
					ReturnTypeText: types.TypeString(resultType, func(pkg *types.Package) string { return pkg.Name() }),
					Line:           start, EndLine: end, Fields: fields,
					Tokens: bodyTokens(fset, file, function), Policy: policy,
					Concerns: concerns, Calls: calls, Object: object, ReturnType: resultType,
				})
			}
		}
	}
	sort.Slice(all, func(i, j int) bool { return all[i].Key < all[j].Key })
	return all, incoming, active
}

func member(value *candidate, incoming map[*types.Func]int) memberRecord {
	return memberRecord{
		File: value.File, QualifiedName: value.Name, Line: value.Line,
		EndLine: value.EndLine, Size: value.EndLine - value.Line + 1,
		CallerCount: incoming[value.Object],
	}
}

func reason(value string) *string { return &value }

func pairRecord(left, right *candidate, incoming map[*types.Func]int) findingRecord {
	return findingRecord{
		Level: "function", Members: []memberRecord{member(left, incoming), member(right, incoming)},
		StaticReturnType: left.ReturnTypeText, ReturnFields: left.Fields,
		Similarity: lexicalSimilarity(left.Tokens, right.Tokens),
	}
}

func triage(candidates []*candidate, incoming map[*types.Func]int) ([]findingRecord, []findingRecord, []findingRecord) {
	confirmed := []findingRecord{}
	uncertain := []findingRecord{}
	rejected := []findingRecord{}
	nextID := 1
	for leftIndex := 0; leftIndex < len(candidates); leftIndex++ {
		for rightIndex := leftIndex + 1; rightIndex < len(candidates); rightIndex++ {
			left, right := candidates[leftIndex], candidates[rightIndex]
			if !types.Identical(left.ReturnType, right.ReturnType) || !equalStrings(left.Fields, right.Fields) {
				continue
			}
			record := pairRecord(left, right, incoming)
			if left.Calls[right.Object] || right.Calls[left.Object] {
				record.InvestigationStatus = "rejected"
				record.ReasonCode = reason("caller_callee")
				record.Notes = "A go/types-resolved direct call makes this a caller/callee relationship, not parallel duplication."
				rejected = append(rejected, record)
				continue
			}
			if record.Similarity >= 0.9 {
				record.InvestigationStatus = "rejected"
				record.ReasonCode = reason("token_similar_belongs_in_find_duplication")
				record.Notes = "The function body token sets are near-identical; this belongs in lexical duplication triage."
				rejected = append(rejected, record)
				continue
			}
			if !equalStrings(left.Policy, right.Policy) {
				record.InvestigationStatus = "rejected"
				record.ReasonCode = reason("load_bearing_divergence")
				record.Notes = "The panic, recover, defer, or goroutine policy differs and may be caller-visible."
				rejected = append(rejected, record)
				continue
			}
			concerns := append(append([]string{}, left.Concerns...), right.Concerns...)
			sort.Strings(concerns)
			if len(concerns) > 0 {
				record.InvestigationStatus = "uncertain"
				record.ReasonCode = reason("direct_call_unresolved_or_dynamic")
				record.Notes = "Direct-call analysis encountered a function-value or otherwise dynamic call."
				uncertain = append(uncertain, record)
				continue
			}
			id := fmt.Sprintf("GO-SD-%04d", nextID)
			nextID++
			record.FindingID, record.ID = id, id
			record.InvestigationStatus = "confirmed"
			record.SharedCoreDescription = fmt.Sprintf("Both statically typed functions return %s with %s through different implementation shapes.", left.ReturnTypeText, strings.Join(left.Fields, ", "))
			record.Divergence = map[string][]string{"accidental": {}, "load_bearing": {}}
			record.ConsolidationShape = "share_utilities"
			record.MaintenanceRiskDomain = "unknown"
			record.MatrixPath = "capability_matrices/" + id + ".md"
			record.TestsThatGuardThisArea = []string{}
			record.Notes = "Function-level static review lead only; this is not proof of behavioral equivalence. Review runtime behavior and caller contracts before any refactor."
			confirmed = append(confirmed, record)
		}
	}
	return confirmed, uncertain, rejected
}

func matrix(finding findingRecord) string {
	left, right := finding.Members[0], finding.Members[1]
	return fmt.Sprintf("## %s: %s and %s\n\n### Implementations\n- **A:** `%s:%d-%d` — `%s`\n- **B:** `%s:%d-%d` — `%s`\n\n### Capability comparison\n\n| Capability | A | B | Notes |\n|---|---|---|---|\n| Static result type | %s | %s | go/types reports identical named result types. |\n| Returned fields | %s | %s | Direct composite returns contain the same named fields. |\n| Resolved direct call relationship | None | None | go/types does not make either member the other's wrapper. |\n| Panic / defer / goroutine policy | Same | Same | No incompatible static policy marker was detected. |\n\n### Recommendation\n\nReview the lead with a human. It is not proof of behavioral equivalence or an automatic refactor.\n",
		finding.FindingID, left.QualifiedName, right.QualifiedName,
		left.File, left.Line, left.EndLine, left.QualifiedName,
		right.File, right.Line, right.EndLine, right.QualifiedName,
		finding.StaticReturnType, finding.StaticReturnType,
		strings.Join(finding.ReturnFields, ", "), strings.Join(finding.ReturnFields, ", "))
}

func renderTriage(confirmed, uncertain, rejected []findingRecord) string {
	var output strings.Builder
	output.WriteString("# Go semantic-duplication triage\n\n")
	sections := []struct {
		name  string
		items []findingRecord
	}{{"Confirmed static review leads", confirmed}, {"Uncertain candidates", uncertain}, {"Rejected candidates", rejected}}
	for _, section := range sections {
		fmt.Fprintf(&output, "## %s\n\n", section.name)
		if len(section.items) == 0 {
			output.WriteString("(none)\n\n")
			continue
		}
		for _, finding := range section.items {
			label := finding.FindingID
			if label == "" {
				label = finding.InvestigationStatus
			}
			fmt.Fprintf(&output, "### %s: %s / %s\n\n- **Status:** %s\n- **Evidence:** same resolved result type and returned fields\n- **Notes:** %s\n\n", label, finding.Members[0].QualifiedName, finding.Members[1].QualifiedName, finding.InvestigationStatus, finding.Notes)
		}
	}
	return output.String()
}

func writeJSON(path string, value any) {
	content, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		fatal("cannot encode %s: %v", path, err)
	}
	content = append(content, '\n')
	if err := os.WriteFile(path, content, 0o644); err != nil {
		fatal("cannot write %s: %v", path, err)
	}
}

func main() {
	args := parseArguments()
	root, err := filepath.Abs(args.ProjectRoot)
	if err != nil {
		fatal("invalid project root: %v", err)
	}
	report, err := filepath.Abs(args.ReportDir)
	if err != nil || !within(root, report) {
		fatal("report directory must stay inside project root")
	}
	records, selected := inventory(root, args.Target)
	packages, exports := listPackages(args.GoExecutable, root)
	candidates, incoming, active := collectCandidates(root, packages, exports, selected)
	unavailable := []string{}
	for path := range selected {
		if !active[path] {
			unavailable = append(unavailable, relative(root, path))
		}
	}
	sort.Strings(unavailable)
	status := "complete"
	if len(unavailable) > 0 {
		status = "partial"
	}
	confirmed, uncertain, rejected := triage(candidates, incoming)
	if err := os.MkdirAll(filepath.Join(report, "capability_matrices"), 0o755); err != nil {
		fatal("cannot create report directory: %v", err)
	}
	for _, finding := range confirmed {
		if err := os.WriteFile(filepath.Join(report, finding.MatrixPath), []byte(matrix(finding)), 0o644); err != nil {
			fatal("cannot write capability matrix: %v", err)
		}
	}
	capabilities := map[string]string{
		"function_level_static_candidates": "available",
		"resolved_direct_calls":            "available_for_static_calls",
		"function_value_or_dynamic_calls":  "uncertain",
		"workflow_or_framework_analysis":   "unavailable",
		"method_or_interface_semantics":    "unavailable",
	}
	payload := map[string]any{
		"skill": "find-semantic-duplication", "language": "go",
		"analyzer": "go-list-go-parser-go-types", "status": status,
		"capability_matrix": capabilities,
		"counts":            map[string]int{"confirmed": len(confirmed), "uncertain": len(uncertain), "rejected": len(rejected)},
		"findings":          confirmed, "confirmed": confirmed, "uncertain": uncertain, "rejected": rejected,
	}
	analysis := map[string]any{
		"language": "go", "analyzer": "go-list-go-parser-go-types", "status": status,
		"source_inventory": records, "unavailable_files": unavailable,
		"eligible_function_count": len(candidates), "capability_matrix": capabilities,
	}
	writeJSON(filepath.Join(report, "analysis.json"), analysis)
	writeJSON(filepath.Join(report, "findings.json"), payload)
	if err := os.WriteFile(filepath.Join(report, "triage.md"), []byte(renderTriage(confirmed, uncertain, rejected)), 0o644); err != nil {
		fatal("cannot write triage: %v", err)
	}
}
