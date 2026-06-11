class StartDownloadView:
    def post(self, request):
        task.delay(request.site_id)
        return {"ok": True}
