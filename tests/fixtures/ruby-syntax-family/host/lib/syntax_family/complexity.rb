# frozen_string_literal: true

module SyntaxFamily
  module Complexity
    def self.route_invoice(value)
      score = value
      if value > 0
        score += 1
      end
      if value > 1
        score += 1
      end
      if value > 2
        score += 1
      end
      if value > 3
        score += 1
      end
      if value > 4
        score += 1
      end
      if value > 5
        score += 1
      end
      if value > 6
        score += 1
      end
      if value > 7
        score += 1
      end
      if value > 8
        score += 1
      end
      score
    end

    def self.block_decoy(value)
      deferred = lambda do |candidate|
        if candidate > 0
          1
        elsif candidate > 1
          2
        elsif candidate > 2
          3
        elsif candidate > 3
          4
        elsif candidate > 4
          5
        elsif candidate > 5
          6
        elsif candidate > 6
          7
        elsif candidate > 7
          8
        end
      end
      deferred.call(value)
    end
  end
end
