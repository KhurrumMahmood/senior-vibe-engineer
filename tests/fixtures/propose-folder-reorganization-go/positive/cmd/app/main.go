package main

import (
	"fmt"

	legacy "example.com/folder-reorg/internal/legacy"
)

func main() {
	fmt.Println(legacy.Summary(legacy.ParseInvoice(4)))
}
