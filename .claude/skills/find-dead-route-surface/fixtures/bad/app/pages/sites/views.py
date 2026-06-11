class SitePrototypeView:
    template_name = "core/missing.html"

    @classmethod
    def as_view(cls):
        return cls()
