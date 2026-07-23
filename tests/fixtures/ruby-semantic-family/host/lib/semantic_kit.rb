# frozen_string_literal: true

require_relative "semantic/dormant_plan"
require_relative "semantic/job"
require_relative "semantic/sweep_options"
require_relative "semantic/sweep_runner"
require_relative "semantic/duplicate_alpha"
require_relative "semantic/duplicate_beta"
require_relative "semantic/duplicate_callers"
require_relative "semantic/invoice_record"
require_relative "semantic/legacy_invoice"
require_relative "semantic/dynamic_boundary"

module SemanticKit
  VERSION = "0.1.0"
end
