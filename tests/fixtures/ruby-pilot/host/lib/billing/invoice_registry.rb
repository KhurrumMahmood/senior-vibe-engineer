# frozen_string_literal: true

module Billing
  class InvoiceRegistry
    # Returns a stable label for a known invoice identifier.
    def label_for(identifier)
      "invoice:#{identifier}"
    end
  end
end
