# frozen_string_literal: true

require_relative "../lib/billing/invoice_service"

service = Billing::InvoiceService.new
actual = service.render("INV-42", 50_000)
expected = "invoice:INV-42:125"
raise "expected #{expected.inspect}, got #{actual.inspect}" unless actual == expected

puts "native-test:ok"
