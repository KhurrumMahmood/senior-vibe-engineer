# frozen_string_literal: true

module SemanticKit
  class SweepOptions
    attr_reader :audit

    def initialize(audit: false)
      @audit = audit
    end
  end
end
