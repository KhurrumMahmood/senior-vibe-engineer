# frozen_string_literal: true

require "syntax_family"

raise "complexity mismatch" unless SyntaxFamily::Complexity.route_invoice(9) == 18
raise "standard mismatch" unless SyntaxFamily::Standards.handled_parse == 7

puts "ruby-syntax-native-test:ok"
