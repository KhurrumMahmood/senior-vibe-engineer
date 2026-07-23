# frozen_string_literal: true

module Billing
  class Parser
    def cancelled_order
      :cancelled_invoice
    end

    def pending_total(items)
      subtotal = items.sum
      fee = 125
      tax = 75
      discount = 0
      subtotal + fee + tax - discount
    end
  end
end
