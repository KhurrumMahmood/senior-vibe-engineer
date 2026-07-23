String parseBillingState(String value) {
  return 'cancelled_order:${value.trim()}';
}

const unrelatedSubstring = 'cancelled_orders';
