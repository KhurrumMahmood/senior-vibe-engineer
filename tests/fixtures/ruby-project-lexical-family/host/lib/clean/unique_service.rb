# frozen_string_literal: true

module Clean
  class UniqueService
    def unique_total(items)
      subtotal = items.sum
      surcharge = 9
      subtotal + surcharge
    end
  end
end
