# frozen_string_literal: true

module Billing
  module Formatting
    def formatted(identifier) = "invoice:#{identifier}"
  end

  module FactoryMethods
    def build = new
  end

  module Audited
    def render(identifier)
      super
    end
  end
end
