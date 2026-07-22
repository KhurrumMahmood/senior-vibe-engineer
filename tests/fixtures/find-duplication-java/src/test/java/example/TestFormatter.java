package example;

public class TestFormatter {
    public String summarize(java.util.List<String> values) {
        String result = "";
        for (String value : values) {
            result += value.trim();
        }
        return result;
    }
}
