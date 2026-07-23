# frozen_string_literal: true

module SemanticKit
  class InvoiceRecord
    def initialize(identifier)
      @identifier = identifier
    end

    def label = "invoice:#{@identifier}"
  end
end
