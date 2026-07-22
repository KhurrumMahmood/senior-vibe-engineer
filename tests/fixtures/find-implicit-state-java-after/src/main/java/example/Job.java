package example;

public final class Job {
    public JobStatus status;

    public boolean advance() {
        status = JobStatus.QUEUED;
        return status == JobStatus.QUEUED || status == JobStatus.RUNNING || status == JobStatus.DONE;
    }
}
