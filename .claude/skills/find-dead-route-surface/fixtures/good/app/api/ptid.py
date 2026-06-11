class SitePtidView:
    template_name = "core/ptid.html"

    @classmethod
    def as_view(cls):
        return cls()
