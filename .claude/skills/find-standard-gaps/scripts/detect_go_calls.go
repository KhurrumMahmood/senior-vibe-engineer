// Extract direct Go call syntax and defer enclosure for find-standard-gaps.
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
	"runtime"
	"strings"
)

type callRecord struct {
	Name    string `json:"name"`
	Line    int    `json:"line"`
	Text    string `json:"text"`
	InDefer bool   `json:"in_defer"`
}

type payload struct {
	SchemaVersion int           `json:"schema_version"`
	Analyzer      string        `json:"analyzer"`
	GoVersion     string        `json:"go_version"`
	Files         []filePayload `json:"files"`
}

type filePayload struct {
	File    string       `json:"file"`
	Status  string       `json:"status"`
	Error   string       `json:"error,omitempty"`
	Records []callRecord `json:"records"`
}

type visitor struct {
	fset    *token.FileSet
	lines   []string
	records *[]callRecord
}

func fail(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "[detect_go_calls] "+format+"\n", args...)
	os.Exit(2)
}

func dotted(expression ast.Expr) string {
	switch typed := expression.(type) {
	case *ast.Ident:
		return typed.Name
	case *ast.SelectorExpr:
		base := dotted(typed.X)
		if base == "" {
			return ""
		}
		return base + "." + typed.Sel.Name
	case *ast.IndexExpr:
		return dotted(typed.X)
	case *ast.IndexListExpr:
		return dotted(typed.X)
	case *ast.ParenExpr:
		return dotted(typed.X)
	default:
		return ""
	}
}

func (current *visitor) record(call *ast.CallExpr, inDefer bool) {
	name := dotted(call.Fun)
	if name == "" {
		return
	}
	line := current.fset.PositionFor(call.Pos(), true).Line
	text := ""
	if line > 0 && line <= len(current.lines) {
		text = strings.TrimSpace(current.lines[line-1])
	}
	*current.records = append(*current.records, callRecord{
		Name: name, Line: line, Text: text, InDefer: inDefer,
	})
}

func (current *visitor) Visit(node ast.Node) ast.Visitor {
	if node == nil {
		return nil
	}
	if deferred, ok := node.(*ast.DeferStmt); ok {
		// Only the direct CallExpr is deferred. Calls used to evaluate its
		// receiver or arguments execute immediately and must not inherit the
		// satisfaction flag.
		current.record(deferred.Call, true)
		ast.Walk(current, deferred.Call.Fun)
		for _, argument := range deferred.Call.Args {
			ast.Walk(current, argument)
		}
		return nil
	}
	if call, ok := node.(*ast.CallExpr); ok {
		current.record(call, false)
	}
	return current
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

var constrainedSuffixes = map[string]bool{
	"386": true, "aix": true, "amd64": true, "android": true,
	"arm": true, "arm64": true, "darwin": true, "dragonfly": true,
	"freebsd": true, "illumos": true, "ios": true, "js": true,
	"linux": true, "loong64": true, "mips": true, "mips64": true,
	"mips64le": true, "mipsle": true, "netbsd": true, "openbsd": true,
	"plan9": true, "ppc64": true, "ppc64le": true, "riscv64": true,
	"s390x": true, "solaris": true, "wasip1": true, "wasm": true,
	"windows": true,
}

func hasConstrainedFilename(path string) bool {
	name := strings.TrimSuffix(filepath.Base(path), ".go")
	name = strings.TrimSuffix(name, "_test")
	parts := strings.Split(name, "_")
	if len(parts) < 2 {
		return false
	}
	return constrainedSuffixes[parts[len(parts)-1]]
}

func analyze(path string) filePayload {
	result := filePayload{File: path, Status: "complete", Records: []callRecord{}}
	source, err := os.ReadFile(path)
	if err != nil {
		result.Status = "read-error"
		result.Error = err.Error()
		return result
	}
	fset := token.NewFileSet()
	parsed, err := parser.ParseFile(
		fset,
		path,
		source,
		parser.ParseComments|parser.AllErrors|parser.SkipObjectResolution,
	)
	if err != nil {
		result.Status = "syntax-error"
		result.Error = err.Error()
		return result
	}
	if ast.IsGenerated(parsed) {
		result.Status = "generated"
		return result
	}
	if hasBuildConstraint(parsed) || hasConstrainedFilename(path) {
		result.Status = "build-constraint-ambiguous"
		return result
	}
	ast.Walk(&visitor{
		fset:    fset,
		lines:   strings.Split(string(source), "\n"),
		records: &result.Records,
	}, parsed)
	return result
}

func main() {
	flag.Parse()
	if flag.NArg() == 0 {
		fail("usage: detect_go_calls.go -- <go-source> [<go-source> ...]")
	}
	files := make([]filePayload, 0, flag.NArg())
	for _, path := range flag.Args() {
		files = append(files, analyze(path))
	}
	encoded, err := json.Marshal(payload{
		SchemaVersion: 1,
		Analyzer:      "go-parser-go-ast",
		GoVersion:     runtime.Version(),
		Files:         files,
	})
	if err != nil {
		fail("cannot encode parser result: %v", err)
	}
	fmt.Println(string(encoded))
}
