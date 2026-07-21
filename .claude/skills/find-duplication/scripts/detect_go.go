// Detect exact normalized Go function-body clones for find-duplication.
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"go/ast"
	"go/format"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

type functionRecord struct {
	Name        string `json:"name"`
	StartLine   int    `json:"start_line"`
	EndLine     int    `json:"end_line"`
	LOC         int    `json:"loc"`
	Fingerprint string `json:"fingerprint"`
}

type fileRecord struct {
	File      string           `json:"file"`
	Status    string           `json:"status"`
	Error     string           `json:"error,omitempty"`
	Functions []functionRecord `json:"functions"`
}

type payload struct {
	SchemaVersion int          `json:"schema_version"`
	Analyzer      string       `json:"analyzer"`
	GoVersion     string       `json:"go_version"`
	Files         []fileRecord `json:"files"`
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

func receiverName(expr ast.Expr) string {
	switch value := expr.(type) {
	case *ast.Ident:
		return value.Name
	case *ast.StarExpr:
		return receiverName(value.X)
	case *ast.IndexExpr:
		return receiverName(value.X)
	case *ast.IndexListExpr:
		return receiverName(value.X)
	default:
		return "receiver"
	}
}

func analyze(path string) fileRecord {
	result := fileRecord{File: path, Status: "complete", Functions: []functionRecord{}}
	fset := token.NewFileSet()
	file, err := parser.ParseFile(
		fset, path, nil,
		parser.ParseComments|parser.AllErrors|parser.SkipObjectResolution,
	)
	if err != nil {
		result.Status = "syntax-error"
		result.Error = err.Error()
		return result
	}
	if ast.IsGenerated(file) {
		result.Status = "generated"
		return result
	}
	if hasBuildConstraint(file) || constrainedFilename(path) {
		result.Status = "build-constraint-ambiguous"
		return result
	}
	for _, declaration := range file.Decls {
		function, ok := declaration.(*ast.FuncDecl)
		if !ok || function.Name == nil || function.Body == nil {
			continue
		}
		start := fset.PositionFor(function.Pos(), true).Line
		end := fset.PositionFor(function.End(), true).Line
		loc := end - start + 1
		if loc < 5 {
			continue
		}
		var normalized bytes.Buffer
		if err := format.Node(&normalized, fset, function.Body); err != nil {
			result.Status = "format-error"
			result.Error = err.Error()
			result.Functions = []functionRecord{}
			return result
		}
		digest := sha256.Sum256(normalized.Bytes())
		name := function.Name.Name
		if function.Recv != nil && len(function.Recv.List) > 0 {
			name = receiverName(function.Recv.List[0].Type) + "." + name
		}
		result.Functions = append(result.Functions, functionRecord{
			Name: name, StartLine: start, EndLine: end, LOC: loc,
			Fingerprint: hex.EncodeToString(digest[:]),
		})
	}
	return result
}

func main() {
	flag.Parse()
	if flag.NArg() == 0 {
		fmt.Fprintln(os.Stderr, "usage: detect_go.go -- <go-source> [<go-source> ...]")
		os.Exit(2)
	}
	files := make([]fileRecord, 0, flag.NArg())
	for _, path := range flag.Args() {
		files = append(files, analyze(path))
	}
	if err := json.NewEncoder(os.Stdout).Encode(payload{
		SchemaVersion: 1,
		Analyzer:      "go-parser-exact-function-body",
		GoVersion:     runtime.Version(),
		Files:         files,
	}); err != nil {
		fmt.Fprintf(os.Stderr, "encode detector result: %v\n", err)
		os.Exit(2)
	}
}
