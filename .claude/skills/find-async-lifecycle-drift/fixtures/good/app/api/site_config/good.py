class StartDownloadView:
    def post(self, request):
        active_job = self.find_active_job()
        if active_job:
            return {"job_id": active_job.id}
        task.delay(request.site_id)
        return {"ok": True}
