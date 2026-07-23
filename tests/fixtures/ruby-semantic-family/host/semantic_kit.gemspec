# frozen_string_literal: true

Gem::Specification.new do |spec|
  spec.name = "semantic_kit"
  spec.version = "0.1.0"
  spec.summary = "Plain Ruby RBS semantic family fixture"
  spec.authors = ["Engineering Skills"]
  spec.files = Dir["bin/*", "lib/**/*.rb", "sig/**/*.rbs"]
  spec.bindir = "bin"
  spec.executables = ["semantic-kit-smoke"]
  spec.require_paths = ["lib"]
  spec.required_ruby_version = ">= 3.3"
end
