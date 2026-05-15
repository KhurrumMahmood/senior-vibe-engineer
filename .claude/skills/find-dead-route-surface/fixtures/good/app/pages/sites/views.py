class SiteActiveView:
    template_name = "core/active.html"

    @classmethod
    def as_view(cls):
        return cls()
