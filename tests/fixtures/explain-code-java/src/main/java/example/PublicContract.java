package example;

public interface PublicContract {
    String execute(String value);

    default String identity(String value) {
        return value;
    }
}
