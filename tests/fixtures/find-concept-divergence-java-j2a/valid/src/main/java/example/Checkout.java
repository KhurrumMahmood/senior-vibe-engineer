package example;

final class Checkout {
    private static final String MIGRATION = "legacy checkout";
    private static final String OLD_CART = "old-cart";
    private static final String ACTIVE_CART = "active-cart";
    private static final String ORDER_BASKET = "order basket";
    private static final String CHECKOUT_BASKET = "checkout basket";

    String label() {
        return MIGRATION + OLD_CART + ACTIVE_CART + ORDER_BASKET + CHECKOUT_BASKET;
    }
}
