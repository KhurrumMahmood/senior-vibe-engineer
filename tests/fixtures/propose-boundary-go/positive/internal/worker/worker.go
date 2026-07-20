package worker

import orders "example.com/propose-boundary-go/internal/legacy"

func Capture() int {
	return orders.SettlementCapture(orders.Input{Subtotal: 9})
}
