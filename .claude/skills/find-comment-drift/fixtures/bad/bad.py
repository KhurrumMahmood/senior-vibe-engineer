"""Legacy SiteConfig route helpers."""


class SetupView:
    pass


class GenericService:
    """Service."""

    def run(self):
        return None


# ===== Setup helpers =====

# Get the site
site_name = "demo"

# See app/pages/sites/__init__.py:12 for details.
ROUTE_NAME = site_name
