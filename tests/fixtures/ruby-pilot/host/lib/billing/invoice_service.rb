# frozen_string_literal: true

require_relative "invoice_registry"

module Billing
  class InvoiceService
    def initialize(registry: InvoiceRegistry.new)
      @registry = registry
    end

    # Calculates a percentage fee from the invoice amount.
    def fee_cents(_amount_cents) = 125

    # Formats an invoice label and its fixed fee.
    def render(identifier, amount_cents)
      [@registry.label_for(identifier), fee_cents(amount_cents)].join(":")
    end
  end
end
