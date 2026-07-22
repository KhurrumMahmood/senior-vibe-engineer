# frozen_string_literal: true

module Billing
  module DynamicFeatures
    def self.load_named(path) = require(path)
    def self.constant_named(name) = Object.const_get(name)
    def self.call_named(receiver, name, ...) = receiver.public_send(name, ...)

    def method_missing(name, ...)
      super
    end

    define_method(:generated_label) { |value| "dynamic:#{value}" }
  end
end

Billing::InvoiceService.class_eval do
  def runtime_patch = true
end if defined?(Billing::InvoiceService)
