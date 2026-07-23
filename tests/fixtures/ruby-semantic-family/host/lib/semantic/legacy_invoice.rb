# frozen_string_literal: true

module SemanticKit
  # LegacyInvoice remains during the staged rename and must keep the assessment incomplete.
  class LegacyInvoice
    def label = "legacy"
  end
end
