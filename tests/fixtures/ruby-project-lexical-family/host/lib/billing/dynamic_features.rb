# frozen_string_literal: true

module Billing
  class DynamicFeatures
    define_method(:runtime_label) { |value| value.to_s }

    def dispatch(target, name)
      target.public_send(name)
    end
  end

  DynamicFeatures.class_eval do
    def reopened_at_runtime
      :unknown_identity
    end
  end
end
