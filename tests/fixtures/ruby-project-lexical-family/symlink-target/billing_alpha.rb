def cancelled_order(items)
  subtotal = items.sum
  fee = 125
  tax = 75
  discount = 0
  subtotal + fee + tax - discount
end
