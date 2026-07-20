// Extract syntax-only Go function-complexity facts for find-complexity-hotspots.
//
// This is family-local by design. It uses only the installed host Go toolchain's
// standard library, resolves no imports, and makes no package/type claims.
package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"go/ast"
	"go/parser"
	"go/printer"
	"go/token"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

type functionRecord struct {
	Symbol      string `json:"symbol"`
	Kind        string `json:"kind"`
	BranchScore int    `json:"branch_score"`
	Lineno      int    `json:"lineno"`
	EndLineno   int    `json:"end_lineno"`
	Loc         int    `json:"loc"`
}

type skippedFile struct {
	File   string `json:"file"`
	Reason string `json:"reason"`
}

type result struct {
	SchemaVersion int              `json:"schema_version"`
	Status        string           `json:"status"`
	Analyzer      string           `json:"analyzer"`
	GoVersion     string           `json:"go_version"`
	Records       []functionRecord `json:"records"`
	Skipped       []skippedFile    `json:"skipped"`
}

func fail(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "[detect_go_complexity] "+format+"\n", args...)
	os.Exit(2)
}

func relativePath(projectRoot, file string) string {
	relative, err := filepath.Rel(projectRoot, file)
	if err != nil {
		return filepath.ToSlash(file)
	}
	return filepath.ToSlash(relative)
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

func receiverText(fset *token.FileSet, declaration *ast.FuncDecl) string {
	if declaration.Recv == nil || len(declaration.Recv.List) == 0 {
		return ""
	}
	var buffer bytes.Buffer
	if err := printer.Fprint(&buffer, fset, declaration.Recv.List[0].Type); err != nil {
		fail("cannot render receiver for %s: %v", declaration.Name.Name, err)
	}
	return buffer.String()
}

func branchScore(body *ast.BlockStmt) int {
	score := 0
	ast.Inspect(body, func(node ast.Node) bool {
		if node == nil {
			return true
		}
		if _, nested := node.(*ast.FuncLit); nested {
			return false
		}
		switch typed := node.(type) {
		case *ast.IfStmt, *ast.ForStmt, *ast.RangeStmt, *ast.SwitchStmt, *ast.TypeSwitchStmt, *ast.SelectStmt:
			score++
		case *ast.BinaryExpr:
			if typed.Op == token.LAND || typed.Op == token.LOR {
				score++
			}
		}
		return true
	})
	return score
}

func functions(fset *token.FileSet, file *ast.File) []functionRecord {
	records := []functionRecord{}
	for _, declaration := range file.Decls {
		function, ok := declaration.(*ast.FuncDecl)
		if !ok || function.Name == nil || function.Body == nil {
			continue
		}
		start := fset.PositionFor(function.Pos(), true).Line
		end := fset.PositionFor(function.End(), true).Line
		kind := "function"
		symbol := function.Name.Name
		if receiver := receiverText(fset, function); receiver != "" {
			kind = "method"
			symbol = "(" + receiver + ")." + function.Name.Name
		}
		records = append(records, functionRecord{
			Symbol:      symbol,
			Kind:        kind,
			BranchScore: branchScore(function.Body),
			Lineno:      start,
			EndLineno:   end,
			Loc:         max(1, end-start+1),
		})
	}
	return records
}

func main() {
	fileFlag := flag.String("file", "", "Go source file")
	projectRootFlag := flag.String("project-root", "", "project root")
	flag.Parse()
	if *fileFlag == "" || *projectRootFlag == "" || flag.NArg() != 0 {
		fail("usage: detect_go_complexity.go --file <go-source> --project-root <path>")
	}
	filePath, err := filepath.Abs(*fileFlag)
	if err != nil {
		fail("cannot resolve source path: %v", err)
	}
	projectRoot, err := filepath.Abs(*projectRootFlag)
	if err != nil {
		fail("cannot resolve project root: %v", err)
	}
	if strings.ToLower(filepath.Ext(filePath)) != ".go" {
		fail("Go source has an unsupported suffix: %s", filePath)
	}
	if _, err := os.Stat(filePath); err != nil {
		fail("source does not exist: %s", filePath)
	}

	fset := token.NewFileSet()
	parsed, err := parser.ParseFile(
		fset,
		filePath,
		nil,
		parser.ParseComments|parser.AllErrors|parser.SkipObjectResolution,
	)
	if err != nil {
		fail("syntax error in %s: %v", relativePath(projectRoot, filePath), err)
	}

	payload := result{
		SchemaVersion: 1,
		Status:        "complete",
		Analyzer:      "go-parser-go-ast",
		GoVersion:     runtime.Version(),
		Records:       []functionRecord{},
		Skipped:       []skippedFile{},
	}
	if hasBuildConstraint(parsed) {
		payload.Status = "partial"
		payload.Skipped = append(payload.Skipped, skippedFile{
			File: relativePath(projectRoot, filePath), Reason: "build-constraint-ambiguous",
		})
	} else if ast.IsGenerated(parsed) {
		payload.Skipped = append(payload.Skipped, skippedFile{
			File: relativePath(projectRoot, filePath), Reason: "generated_marker",
		})
	} else {
		payload.Records = functions(fset, parsed)
	}

	encoded, err := json.Marshal(payload)
	if err != nil {
		fail("cannot encode parser result: %v", err)
	}
	fmt.Println(string(encoded))
}
