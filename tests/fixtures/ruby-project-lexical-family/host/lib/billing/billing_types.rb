# frozen_string_literal: true

module Billing
  module InvoiceState
    PENDING = :pending
  end

  class Invoice
    def different_total(items)
      subtotal = items.sum
      fee = 150
      tax = 75
      discount = 0
      subtotal + fee + tax - discount
    end
  end
end
