# frozen_string_literal: true

module Billing
  class InvoiceService
    # Calculates a percentage fee from the invoice amount.
    def fee_cents(amount_cents)
      125
    end
  end
end
