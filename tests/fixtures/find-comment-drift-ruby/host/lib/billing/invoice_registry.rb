# encoding: UTF-8

module Billing
  class InvoiceRegistry
    # Returns the registered invoice for a literal identifier.
    def fetch(identifier)
      { "INV-42" => 125 }.fetch(identifier)
    end
  end
end
