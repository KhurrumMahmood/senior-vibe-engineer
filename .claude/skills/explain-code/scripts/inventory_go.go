package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"go/ast"
	"go/format"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"strings"
)

type target struct {
	Symbol       string `json:"symbol"`
	Kind         string `json:"kind"`
	Line         int    `json:"lineno"`
	LOC          int    `json:"loc"`
	BranchCount  int    `json:"branch_count"`
	HasDocstring bool   `json:"has_docstring"`
}

type unexplained struct {
	File   string `json:"file"`
	Symbol string `json:"symbol"`
	Kind   string `json:"kind"`
	Line   int    `json:"lineno"`
	Reason string `json:"reason"`
}

type result struct {
	Status       string        `json:"status"`
	TotalSymbols int           `json:"total_symbols"`
	Targets      []target      `json:"targets"`
	Unexplained  []unexplained `json:"unexplained"`
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

func branchCount(node ast.Node) int {
	count := 0
	ast.Inspect(node, func(child ast.Node) bool {
		switch value := child.(type) {
		case *ast.IfStmt, *ast.ForStmt, *ast.RangeStmt, *ast.SwitchStmt,
			*ast.TypeSwitchStmt, *ast.SelectStmt, *ast.CaseClause, *ast.CommClause:
			count++
		case *ast.BinaryExpr:
			if value.Op == token.LAND || value.Op == token.LOR {
				count++
			}
		}
		return true
	})
	return count
}

func span(fset *token.FileSet, node ast.Node) (int, int) {
	start := fset.Position(node.Pos()).Line
	end := fset.Position(node.End()).Line
	if end < start {
		end = start
	}
	return start, end - start + 1
}

func hasBuildConstraint(file *ast.File) bool {
	for _, group := range file.Comments {
		if group.End() > file.Package {
			continue
		}
		for _, comment := range group.List {
			text := strings.TrimSpace(comment.Text)
			if strings.HasPrefix(text, "//go:build ") || strings.HasPrefix(text, "// +build ") {
				return true
			}
		}
	}
	return false
}

var knownGOOS = map[string]bool{
	"aix": true, "android": true, "darwin": true, "dragonfly": true,
	"freebsd": true, "illumos": true, "ios": true,
	"js": true, "linux": true, "netbsd": true, "openbsd": true,
	"plan9": true, "solaris": true, "wasip1": true, "windows": true,
}

var knownGOARCH = map[string]bool{
	"386": true, "amd64": true, "arm": true,
	"arm64": true, "loong64": true, "mips": true, "mips64": true,
	"mips64le": true, "mipsle": true, "ppc64": true, "ppc64le": true,
	"riscv64": true, "s390x": true, "wasm": true,
}

func hasFilenameBuildConstraint(path string) bool {
	base := strings.TrimSuffix(filepath.Base(path), ".go")
	parts := strings.Split(base, "_")
	if len(parts) < 2 {
		return false
	}
	last := parts[len(parts)-1]
	return knownGOOS[last] || knownGOARCH[last]
}

func aliasDeclaration(fset *token.FileSet, spec *ast.TypeSpec) string {
	var buffer bytes.Buffer
	if err := format.Node(&buffer, fset, spec); err != nil {
		return "type " + spec.Name.Name + " = <unresolved>"
	}
	return "type " + buffer.String()
}

func declarationCount(file *ast.File) int {
	count := 0
	for _, declaration := range file.Decls {
		switch node := declaration.(type) {
		case *ast.FuncDecl:
			count++
		case *ast.GenDecl:
			for _, rawSpec := range node.Specs {
				switch spec := rawSpec.(type) {
				case *ast.TypeSpec:
					count++
				case *ast.ValueSpec:
					count += len(spec.Names)
				}
			}
		}
	}
	return count
}

func main() {
	filePath := flag.String("file", "", "Go source file to inventory")
	displayPath := flag.String("display", "", "Stable display path")
	flag.Parse()
	if *filePath == "" || *displayPath == "" {
		fmt.Fprintln(os.Stderr, "--file and --display are required")
		os.Exit(2)
	}

	fset := token.NewFileSet()
	file, err := parser.ParseFile(fset, *filePath, nil, parser.ParseComments|parser.AllErrors)
	if err != nil {
		fmt.Fprintf(os.Stderr, "syntax error: %v\n", err)
		os.Exit(2)
	}
	payload := result{Status: "complete", Targets: []target{}, Unexplained: []unexplained{}}
	if hasBuildConstraint(file) || hasFilenameBuildConstraint(*filePath) {
		payload.Status = "partial"
		payload.TotalSymbols = declarationCount(file)
		payload.Unexplained = append(payload.Unexplained, unexplained{
			File:   *displayPath,
			Symbol: *displayPath,
			Kind:   "build-constraint-ambiguous",
			Line:   1,
			Reason: "Go v1 does not select files across build constraints; this file is left unexplained.",
		})
		if err := json.NewEncoder(os.Stdout).Encode(payload); err != nil {
			fmt.Fprintf(os.Stderr, "encode inventory: %v\n", err)
			os.Exit(2)
		}
		return
	}

	for _, declaration := range file.Decls {
		switch node := declaration.(type) {
		case *ast.FuncDecl:
			payload.TotalSymbols++
			if !ast.IsExported(node.Name.Name) {
				continue
			}
			symbol := node.Name.Name
			kind := "function"
			if node.Recv != nil && len(node.Recv.List) > 0 {
				symbol = receiverName(node.Recv.List[0].Type) + "." + node.Name.Name
				kind = "method"
			}
			line, loc := span(fset, node)
			payload.Targets = append(payload.Targets, target{
				Symbol:       symbol,
				Kind:         kind,
				Line:         line,
				LOC:          loc,
				BranchCount:  branchCount(node),
				HasDocstring: node.Doc != nil,
			})
		case *ast.GenDecl:
			for _, rawSpec := range node.Specs {
				switch spec := rawSpec.(type) {
				case *ast.TypeSpec:
					payload.TotalSymbols++
					if !ast.IsExported(spec.Name.Name) {
						continue
					}
					line, loc := span(fset, spec)
					if spec.Assign.IsValid() {
						payload.Status = "partial"
						payload.Unexplained = append(payload.Unexplained, unexplained{
							File:   *displayPath,
							Symbol: aliasDeclaration(fset, spec),
							Kind:   "unresolved-go-alias",
							Line:   line,
							Reason: "Go v1 does not resolve exported type aliases or their imported target behavior.",
						})
						continue
					}
					payload.Targets = append(payload.Targets, target{
						Symbol:       spec.Name.Name,
						Kind:         "type",
						Line:         line,
						LOC:          loc,
						BranchCount:  0,
						HasDocstring: spec.Doc != nil || node.Doc != nil,
					})
				case *ast.ValueSpec:
					line, loc := span(fset, spec)
					for _, name := range spec.Names {
						payload.TotalSymbols++
						if !ast.IsExported(name.Name) {
							continue
						}
						payload.Targets = append(payload.Targets, target{
							Symbol:       name.Name,
							Kind:         "module-var",
							Line:         line,
							LOC:          loc,
							BranchCount:  0,
							HasDocstring: spec.Doc != nil || node.Doc != nil,
						})
					}
				}
			}
		}
	}
	if err := json.NewEncoder(os.Stdout).Encode(payload); err != nil {
		fmt.Fprintf(os.Stderr, "encode inventory: %v\n", err)
		os.Exit(2)
	}
}
