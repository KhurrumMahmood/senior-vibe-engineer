# frozen_string_literal: true

require_relative "../lib/invoice_kit"

parser = Billing::Parser.new
validator = Billing::Validator.new
raise "parser total" unless parser.pending_total([100]) == 300
raise "validator total" unless validator.queued_total([100]) == 300

puts "ruby-native-test:ok"
