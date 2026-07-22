# frozen_string_literal: true

require_relative "../lib/billing/invoice_service"

actual = Billing::InvoiceService.new.render("INV-42")
expected = "{\"label\":\"registered:INV-42\"}"
raise "expected #{expected.inspect}, got #{actual.inspect}" unless actual == expected

puts "native-test:ok"
