# frozen_string_literal: true

module SyntaxFamily
  module Omnibus
    def self.load_credentials
      :credentials
    end

    def self.rotate_credentials
      :credentials
    end

    def self.authorize_admin
      :admin
    end

    def self.validate_admin
      :admin
    end

    def self.render_export
      :export
    end

    def self.write_export
      :export
    end

    def self.save_invoice
      :invoice
    end

    def self.load_invoice
      :invoice
    end
  end
end
