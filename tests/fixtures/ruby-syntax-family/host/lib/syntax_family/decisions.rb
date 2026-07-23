# frozen_string_literal: true

module SyntaxFamily
  module Decisions
    # decision:0001 keeps the Ruby syntax boundary explicit.
    def self.anchored_decision
      :anchored
    end

    # decision:9999 is deliberately orphaned.
    def self.orphaned_decision
      :orphaned
    end

    COMMENT_SHAPED_STRING = "# decision:7777"
  end
end
