"""Site route helpers with durable ownership notes."""


class SiteSetupView:
    """Owns setup-page route payload assembly for the Site workflow."""

    def get(self):
        return None


# Compatibility: older import paths still load this symbol from the page package.
LEGACY_SETUP_VIEW = SiteSetupView
