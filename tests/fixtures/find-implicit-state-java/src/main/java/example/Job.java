package example;

import java.util.Objects;

public final class Job {
    public String status;

    public boolean advance() {
        status = "queued";
        return status.equals("queued")
                || "running".equals(status)
                || Objects.equals(status, "done");
    }
}
