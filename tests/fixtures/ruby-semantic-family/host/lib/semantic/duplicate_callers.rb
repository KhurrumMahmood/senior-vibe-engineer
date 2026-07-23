# frozen_string_literal: true

module SemanticKit
  class AlphaConsumer
    def call = DuplicateAlpha.new.calculate(7)
  end

  class BetaConsumer
    def call = DuplicateBeta.new.calculate(7)
  end
end
