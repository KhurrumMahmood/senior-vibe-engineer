# warn_indent: true

module Billing
  COMMENT_LOOKALIKE = "# Calculates a percentage fee from the invoice amount."
  TEMPLATE = <<~TEXT
    # Calculates a percentage fee from the invoice amount.
    def fake(amount)
      125
    end
  TEXT

  # The fixed fee is intentional while the pilot contract remains flat-rate.
  def self.fixed_fee_cents
    125
  end
end
