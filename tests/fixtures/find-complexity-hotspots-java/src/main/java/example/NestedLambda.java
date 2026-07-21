package example;

import java.util.function.IntUnaryOperator;

public final class NestedLambda {
    public IntUnaryOperator operation() {
        return value -> {
            int result = value;
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
        };
    }
}
