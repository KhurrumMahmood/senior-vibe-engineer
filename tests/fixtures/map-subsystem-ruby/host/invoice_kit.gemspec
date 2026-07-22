# frozen_string_literal: true

Gem::Specification.new do |spec|
  spec.name = "invoice_kit"
  spec.version = "0.1.0"
  spec.summary = "Plain Ruby map-subsystem fixture"
  spec.authors = ["Engineering Skills"]
  spec.files = Dir["bin/*", "lib/**/*.rb"]
  spec.bindir = "bin"
  spec.executables = ["invoice-kit-smoke"]
  spec.require_paths = ["lib"]
  spec.required_ruby_version = ">= 3.3"
end
