# frozen_string_literal: true

module SyntaxFamily
  module Standards
    def self.parse_invoice(value = 7)
      value
    end

    def self.handled_parse
      begin
        parse_invoice
      rescue StandardError
        0
      end
    end

    def self.unhandled_parse
      parse_invoice
    end

    CALL_SHAPED_STRING = "parse_invoice"
  end
end
