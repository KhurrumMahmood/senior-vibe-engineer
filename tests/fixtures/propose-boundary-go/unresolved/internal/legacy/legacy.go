package legacy

import "example.invalid/missing"

func QuotePrice() int { return missing.Price() }

func QuotePreview() string { return "quote" }

func SettlementCapture() int { return 1 }

func SettlementReceipt() string { return "settlement" }
