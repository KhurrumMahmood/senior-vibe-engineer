# frozen_string_literal: true

module SemanticKit
  class Job
    attr_accessor :phase

    def initialize
      @phase = "queued"
    end

    def start
      self.phase = "running"
    end

    def finish
      self.phase = "done"
    end
  end
end
