package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"go/parser"
	"go/token"
	"os"
	"regexp"
	"sort"
	"strings"
)

type reference struct {
	Line        int    `json:"line"`
	ID          string `json:"id"`
	CommentForm string `json:"comment_form"`
}

var decisionReference = regexp.MustCompile(`\bdecision:(\d{4})\b`)

func main() {
	file := flag.String("file", "", "Go source file to parse")
	flag.Parse()
	if *file == "" {
		fmt.Fprintln(os.Stderr, "--file is required")
		os.Exit(2)
	}

	fset := token.NewFileSet()
	parsed, err := parser.ParseFile(fset, *file, nil, parser.ParseComments|parser.AllErrors)
	if err != nil {
		fmt.Fprintf(os.Stderr, "syntax error: %v\n", err)
		os.Exit(2)
	}

	references := make([]reference, 0)
	for _, group := range parsed.Comments {
		for _, comment := range group.List {
			form := "line"
			if strings.HasPrefix(comment.Text, "/*") {
				form = "block"
			}
			for _, match := range decisionReference.FindAllStringSubmatchIndex(comment.Text, -1) {
				position := fset.Position(comment.Slash + token.Pos(match[0]))
				references = append(references, reference{
					Line:        position.Line,
					ID:          comment.Text[match[2]:match[3]],
					CommentForm: form,
				})
			}
		}
	}
	sort.Slice(references, func(i, j int) bool {
		if references[i].Line != references[j].Line {
			return references[i].Line < references[j].Line
		}
		return references[i].ID < references[j].ID
	})
	if err := json.NewEncoder(os.Stdout).Encode(references); err != nil {
		fmt.Fprintf(os.Stderr, "encode references: %v\n", err)
		os.Exit(2)
	}
}
