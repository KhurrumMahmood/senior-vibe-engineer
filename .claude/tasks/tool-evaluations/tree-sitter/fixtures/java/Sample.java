package demo;

import java.util.List;

final class Sample {
    Sample() {}

    int compute(int value) {
        return helper(value);
    }

    int helper(int value) {
        return value + 1;
    }
}
