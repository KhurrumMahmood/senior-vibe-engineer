package example.dormant;

public final class Dormant {
    private void unusedPrivate() {
    }

    private void usedPrivate() {
    }

    private void dynamicByName() {
    }

    public void run() {
        usedPrivate();
    }

    public Class<?> plugin() throws ClassNotFoundException {
        String methodName = "dynamicByName";
        return Class.forName(methodName);
    }
}
