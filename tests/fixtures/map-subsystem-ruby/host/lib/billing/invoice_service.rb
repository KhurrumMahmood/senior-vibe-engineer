# frozen_string_literal: true

require "json"
require_relative "mixins"
require_relative "invoice_registry"

module Billing
  class InvoiceService
    include Formatting
    extend FactoryMethods
    prepend Audited

    def initialize(registry: InvoiceRegistry.new)
      @registry = registry
    end

    def render(identifier)
      JSON.generate(label: @registry.label_for(identifier))
    end
  end
end
