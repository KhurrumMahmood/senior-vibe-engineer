# frozen_string_literal: true

module Billing
  module DynamicFeatures
    module_function

    # These valid Ruby shapes are semantic refusal sentinels, not map or rename facts.
    def load_named(path) = require(path)
    def constant_named(name) = Object.const_get(name)
    def call_named(receiver, name, ...) = receiver.public_send(name, ...)

    define_method(:runtime_label) { |value| "dynamic:#{value}" }
  end
end

Billing::InvoiceService.class_eval do
  def reopened_at_runtime = true
end if defined?(Billing::InvoiceService)
