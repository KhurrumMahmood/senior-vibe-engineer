package example;

public final class ComplexityService {
    private int seed;

    public ComplexityService(int value) {
        if (value > 0) seed++;
        if (value > 1) seed++;
        if (value > 2) seed++;
        if (value > 3) seed++;
        if (value > 4) seed++;
        if (value > 5) seed++;
        if (value > 6) seed++;
        if (value > 7) seed++;
        if (value > 8) seed++;
        if (value > 9) seed++;
        if (value > 10) seed++;
        if (value > 11) seed++;
        if (value > 12) seed++;
        if (value > 13) seed++;
        if (value > 14) seed++;
        if (value > 15) seed++;
        if (value > 16) seed++;
        if (value > 17) seed++;
    }

    public int declaredHotspot(int value) {
        int result = seed;
        if (value > 0) result++;
        if (value > 1) result++;
        if (value > 2) result++;
        if (value > 3) result++;
        if (value > 4) result++;
        if (value > 5) result++;
        if (value > 6) result++;
        if (value > 7) result++;
        if (value > 8) result++;
        if (value > 9) result++;
        if (value > 10) result++;
        if (value > 11) result++;
        if (value > 12) result++;
        if (value > 13) result++;
        if (value > 14) result++;
        if (value > 15) result++;
        if (value > 16) result++;
        if (value > 17) result++;
        return result;
    }
}
