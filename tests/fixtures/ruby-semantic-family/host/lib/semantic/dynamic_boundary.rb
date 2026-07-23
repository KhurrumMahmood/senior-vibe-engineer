# frozen_string_literal: true

module SemanticKit
  class DynamicBoundary
    def call_named(receiver, name, ...)
      receiver.public_send(name, ...)
    end
  end
end
