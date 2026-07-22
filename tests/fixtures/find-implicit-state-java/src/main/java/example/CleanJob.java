package example;

enum JobPhase {
    QUEUED,
    RUNNING,
    DONE
}

public final class CleanJob {
    public JobPhase phase;

    public boolean queued() {
        return phase == JobPhase.QUEUED;
    }
}
