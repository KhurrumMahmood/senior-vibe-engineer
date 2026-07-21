using System;

namespace Demo;

internal sealed class Sample
{
    public Sample() {}

    public int Compute(int value)
    {
        return Helper(value);
    }

    private int Helper(int value)
    {
        return value + 1;
    }
}
