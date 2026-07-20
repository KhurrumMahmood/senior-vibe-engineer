package checkout

const migrationLabel = "legacy checkout"

const oldCart = "old-cart"
const activeCart = "active-cart"

const orderBasket = "order basket"
const checkoutBasket = "checkout basket"

func label() string {
	return migrationLabel + oldCart + activeCart + orderBasket + checkoutBasket
}
