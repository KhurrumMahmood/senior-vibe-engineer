# frozen_string_literal: true

require_relative "../lib/semantic_kit"

job = SemanticKit::Job.new
job.start
job.finish
raise "wrong phase" unless job.phase == "done"
raise "wrong label" unless SemanticKit::SweepRunner.new.complete.label == "invoice:INV-7"

puts "ruby-semantic-native-test:ok"
