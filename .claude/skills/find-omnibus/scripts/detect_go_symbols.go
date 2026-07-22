// Extract syntax-only top-level Go function facts for find-omnibus.
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

type symbol struct {
	Name        string `json:"name"`
	ClusterName string `json:"cluster_name"`
	Kind        string `json:"kind"`
	Line        int    `json:"lineno"`
	EndLine     int    `json:"end_lineno"`
	Loc         int    `json:"loc"`
}

type payload struct {
	SchemaVersion int           `json:"schema_version"`
	Analyzer      string        `json:"analyzer"`
	GoVersion     string        `json:"go_version"`
	Files         []filePayload `json:"files"`
}

type filePayload struct {
	File    string   `json:"file"`
	Status  string   `json:"status"`
	Error   string   `json:"error,omitempty"`
	Symbols []symbol `json:"symbols"`
}

func fail(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "[detect_go_symbols] "+format+"\n", args...)
	os.Exit(2)
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
	result := filePayload{File: path, Status: "complete", Symbols: []symbol{}}
	fset := token.NewFileSet()
	parsed, err := parser.ParseFile(
		fset,
		path,
		nil,
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
		result.Status = "build-constraint-unsupported"
		return result
	}
	for _, declaration := range parsed.Decls {
		function, ok := declaration.(*ast.FuncDecl)
		if !ok || function.Name == nil || function.Body == nil {
			continue
		}
		start := fset.PositionFor(function.Pos(), true).Line
		end := fset.PositionFor(function.End(), true).Line
		kind := "function"
		name := function.Name.Name
		if function.Recv != nil {
			kind = "method"
		}
		result.Symbols = append(result.Symbols, symbol{
			Name: name, ClusterName: function.Name.Name, Kind: kind,
			Line: start, EndLine: end, Loc: max(1, end-start+1),
		})
	}
	return result
}

func main() {
	flag.Parse()
	if flag.NArg() == 0 {
		fail("usage: detect_go_symbols.go -- <go-source> [<go-source> ...]")
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
