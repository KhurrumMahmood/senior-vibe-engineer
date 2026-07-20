// Inspect the deliberately small Go package-move surface for move-path.
//
// It is intentionally a helper, not a general Go refactoring engine.  The
// Python mover owns the filesystem transaction; this program establishes the
// only source edits that are allowed: exact import-path string literals.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

type blocked struct {
	Kind   string `json:"kind"`
	Path   string `json:"path,omitempty"`
	Detail string `json:"detail,omitempty"`
}

type span struct {
	File       string `json:"file"`
	Line       int    `json:"line"`
	Start      int    `json:"start"`
	End        int    `json:"end"`
	Old        string `json:"old"`
	New        string `json:"new"`
	OldLiteral string `json:"old_literal"`
	NewLiteral string `json:"new_literal"`
}

type sourceFile struct {
	Path      string
	Dir       string
	Name      string
	Generated bool
	Text      []byte
	AST       *ast.File
	Set       *token.FileSet
}

type output struct {
	Status     string    `json:"status"`
	Error      string    `json:"error,omitempty"`
	OldImport  string    `json:"old_import,omitempty"`
	NewImport  string    `json:"new_import,omitempty"`
	GoFiles    []string  `json:"go_files"`
	MovedFiles []string  `json:"moved_files"`
	Spans      []span    `json:"spans"`
	Blocked    []blocked `json:"blocked"`
}

func rel(root, path string) string {
	value, err := filepath.Rel(root, path)
	if err != nil {
		return path
	}
	return filepath.ToSlash(value)
}

func hasGoBuildDirective(text []byte) bool {
	for _, line := range strings.Split(string(text), "\n") {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "//go:build") || strings.HasPrefix(trimmed, "// +build") {
			return true
		}
	}
	return false
}

func hasDirective(text []byte, directive string) bool {
	return strings.Contains(string(text), directive)
}

func generated(text []byte) bool {
	for _, line := range strings.Split(string(text), "\n") {
		if strings.HasPrefix(strings.TrimSpace(line), "// Code generated ") && strings.Contains(line, "DO NOT EDIT.") {
			return true
		}
	}
	return false
}

func under(path, parent string) bool {
	return path == parent || strings.HasPrefix(path, parent+"/")
}

func addUnique(items []string, value string) []string {
	for _, item := range items {
		if item == value {
			return items
		}
	}
	return append(items, value)
}

func parseFiles(root string, blocks *[]blocked) ([]sourceFile, error) {
	var files []sourceFile
	err := filepath.WalkDir(root, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		relPath := rel(root, path)
		if entry.IsDir() {
			if path != root && (entry.Name() == ".git" || entry.Name() == ".engineering" || entry.Name() == "vendor") {
				return filepath.SkipDir
			}
			if path != root && entry.Name() == "go.mod" {
				return nil
			}
			return nil
		}
		if entry.Type()&os.ModeSymlink != 0 {
			if strings.HasSuffix(entry.Name(), ".go") {
				*blocks = append(*blocks, blocked{Kind: "go_symlink_source", Path: relPath})
			}
			return nil
		}
		if entry.Name() == "go.mod" && path != filepath.Join(root, "go.mod") {
			*blocks = append(*blocks, blocked{Kind: "go_nested_module", Path: relPath})
			return nil
		}
		if !strings.HasSuffix(entry.Name(), ".go") {
			return nil
		}
		text, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		set := token.NewFileSet()
		parsed, err := parser.ParseFile(set, path, text, parser.ParseComments|parser.AllErrors)
		if err != nil {
			return fmt.Errorf("%s: %w", relPath, err)
		}
		files = append(files, sourceFile{
			Path: relPath, Dir: filepath.ToSlash(filepath.Dir(relPath)), Name: entry.Name(),
			Generated: generated(text), Text: text, AST: parsed, Set: set,
		})
		return nil
	})
	return files, err
}

func literalRange(file sourceFile, spec *ast.ImportSpec) (int, int, int, string, bool) {
	if spec.Path == nil {
		return 0, 0, 0, "", false
	}
	value, err := strconv.Unquote(spec.Path.Value)
	if err != nil {
		return 0, 0, 0, "", false
	}
	start := file.Set.Position(spec.Path.Pos())
	end := file.Set.Position(spec.Path.End())
	return start.Offset, end.Offset, start.Line, value, true
}

func main() {
	rootFlag := flag.String("project-root", "", "root Go module")
	from := flag.String("from", "", "source package directory")
	to := flag.String("to", "", "destination package directory")
	module := flag.String("module", "", "module path from go.mod")
	flag.Parse()

	result := output{Status: "unsupported", GoFiles: []string{}, MovedFiles: []string{}, Spans: []span{}, Blocked: []blocked{}}
	if *rootFlag == "" || *from == "" || *to == "" || *module == "" {
		result.Error = "project-root, from, to, and module are required"
		_ = json.NewEncoder(os.Stdout).Encode(result)
		return
	}
	root, err := filepath.Abs(*rootFlag)
	if err != nil {
		result.Error = err.Error()
		_ = json.NewEncoder(os.Stdout).Encode(result)
		return
	}
	fromPath := filepath.ToSlash(filepath.Clean(*from))
	toPath := filepath.ToSlash(filepath.Clean(*to))
	result.OldImport = strings.TrimSuffix(*module, "/") + "/" + fromPath
	result.NewImport = strings.TrimSuffix(*module, "/") + "/" + toPath

	files, err := parseFiles(root, &result.Blocked)
	if err != nil {
		result.Status = "failed"
		result.Error = err.Error()
		_ = json.NewEncoder(os.Stdout).Encode(result)
		return
	}
	for _, file := range files {
		result.GoFiles = addUnique(result.GoFiles, file.Path)
		if under(file.Path, fromPath) {
			result.MovedFiles = addUnique(result.MovedFiles, file.Path)
		}
	}
	if len(result.MovedFiles) == 0 {
		result.Blocked = append(result.Blocked, blocked{Kind: "go_package_has_no_source", Path: fromPath})
	}

	primary := ""
	for _, file := range files {
		moved := under(file.Path, fromPath)
		if moved && file.Dir != fromPath {
			result.Blocked = append(result.Blocked, blocked{Kind: "go_package_tree_unsupported", Path: file.Path})
		}
		if !moved {
			continue
		}
		if file.Generated {
			result.Blocked = append(result.Blocked, blocked{Kind: "go_generated_source", Path: file.Path})
		}
		if hasGoBuildDirective(file.Text) {
			result.Blocked = append(result.Blocked, blocked{Kind: "go_build_constraint", Path: file.Path})
		}
		if hasDirective(file.Text, "//go:generate") {
			result.Blocked = append(result.Blocked, blocked{Kind: "go_generate_directive", Path: file.Path})
		}
		if !strings.HasSuffix(file.Name, "_test.go") {
			if primary == "" {
				primary = file.AST.Name.Name
			} else if primary != file.AST.Name.Name {
				result.Blocked = append(result.Blocked, blocked{Kind: "go_package_name_ambiguous", Path: file.Path})
			}
		}
	}
	if primary == "" {
		result.Blocked = append(result.Blocked, blocked{Kind: "go_package_has_no_non_test_source", Path: fromPath})
	} else if primary == "main" {
		result.Blocked = append(result.Blocked, blocked{Kind: "go_main_package", Path: fromPath})
	}

	for _, file := range files {
		moved := under(file.Path, fromPath)
		accepted := [][2]int{}
		importsOld := false
		for _, spec := range file.AST.Imports {
			start, end, line, value, ok := literalRange(file, spec)
			if !ok {
				result.Blocked = append(result.Blocked, blocked{Kind: "go_import_literal_invalid", Path: file.Path})
				continue
			}
			if value == "C" && moved {
				result.Blocked = append(result.Blocked, blocked{Kind: "go_cgo_package", Path: file.Path})
			}
			if value != result.OldImport {
				continue
			}
			importsOld = true
			accepted = append(accepted, [2]int{start, end})
			result.Spans = append(result.Spans, span{
				File: file.Path, Line: line, Start: start, End: end, Old: value, New: result.NewImport,
				OldLiteral: spec.Path.Value, NewLiteral: strconv.Quote(result.NewImport),
			})
		}
		if moved && strings.HasSuffix(file.Name, "_test.go") && primary != "" && file.AST.Name.Name != primary && file.AST.Name.Name != primary+"_test" {
			result.Blocked = append(result.Blocked, blocked{Kind: "go_test_package_ambiguous", Path: file.Path})
		}
		if importsOld && file.Generated {
			result.Blocked = append(result.Blocked, blocked{Kind: "go_generated_importer", Path: file.Path})
		}
		if importsOld && hasGoBuildDirective(file.Text) {
			result.Blocked = append(result.Blocked, blocked{Kind: "go_build_constraint_importer", Path: file.Path})
		}
		if importsOld && hasDirective(file.Text, "//go:generate") {
			result.Blocked = append(result.Blocked, blocked{Kind: "go_generate_importer", Path: file.Path})
		}
		for offset := 0; ; {
			index := strings.Index(string(file.Text[offset:]), result.OldImport)
			if index < 0 {
				break
			}
			start := offset + index
			end := start + len(result.OldImport)
			insideImport := false
			for _, pair := range accepted {
				if start >= pair[0] && end <= pair[1] {
					insideImport = true
					break
				}
			}
			if !insideImport {
				result.Blocked = append(result.Blocked, blocked{Kind: "go_dynamic_old_path", Path: file.Path})
				break
			}
			offset = end
		}
	}

	sort.Strings(result.GoFiles)
	sort.Strings(result.MovedFiles)
	sort.Slice(result.Spans, func(i, j int) bool {
		if result.Spans[i].File == result.Spans[j].File {
			return result.Spans[i].Start < result.Spans[j].Start
		}
		return result.Spans[i].File < result.Spans[j].File
	})
	if len(result.Blocked) == 0 {
		result.Status = "complete"
	} else {
		for _, item := range result.Blocked {
			if item.Kind == "go_dynamic_old_path" {
				result.Status = "partial"
				_ = json.NewEncoder(os.Stdout).Encode(result)
				return
			}
		}
	}
	_ = json.NewEncoder(os.Stdout).Encode(result)
}
