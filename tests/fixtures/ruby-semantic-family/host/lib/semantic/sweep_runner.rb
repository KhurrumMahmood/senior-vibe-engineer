# frozen_string_literal: true

module SemanticKit
  class SweepRunner
    def first = SweepOptions.new(audit: true)
    def second = SweepOptions.new(audit: true)
    def third = SweepOptions.new(audit: true)
    def straggler = SweepOptions.new

    def complete = InvoiceRecord.new("INV-7")
  end
end
