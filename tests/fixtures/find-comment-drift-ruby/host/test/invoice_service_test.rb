# frozen_string_literal: true

require_relative "../lib/billing/invoice_service"

abort "unexpected fee" unless Billing::InvoiceService.new.fee_cents(10_000) == 125
puts "ruby-test:ok"
