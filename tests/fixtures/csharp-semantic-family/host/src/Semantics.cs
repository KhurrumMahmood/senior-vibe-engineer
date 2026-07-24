using System;

namespace CSharpSemantic;

public interface IProcessor
{
    string Process(int value);
}

public sealed class Processor : IProcessor
{
    public string Process(int value) => $"number:{value}";

    public string Process(string value) => $"text:{value}";
}

public class BaseFormatter
{
    public virtual string Format(int value) => $"base:{value}";
}

public sealed class OverrideFormatter : BaseFormatter
{
    public override string Format(int value) => $"override:{value}";
}

public partial class PartialFeature
{
    public string First() => "first";
}

public partial class PartialFeature
{
    public string Second() => "second";
}

public enum LegacyStatus
{
    Queued,
    Done,
}

public enum CanonicalStatus
{
    Queued,
    Done,
}

public sealed class Job
{
    public string Status { get; private set; } = "queued";

    public void Start() => Status = "running";

    public void Complete() => Status = "done";
}

public sealed record SweepOptions(bool Audit = false, string Region = "us");

public static class SemanticCases
{
    private static int DormantAdjustment(int value) => value + 1;

    private static int CallbackAdjustment(int value) => value + 2;

    public static Func<int, int> Callback() => CallbackAdjustment;

    public static SweepOptions FirstSweep() => new(Audit: true);

    public static SweepOptions SecondSweep() => new(Audit: true, Region: "eu");

    public static SweepOptions SweepStraggler() => new();

    public static string SummarizeAlpha(int amount)
    {
        return $"receipt:{amount}";
    }

    public static string SummarizeBeta(int amount)
    {
        return $"receipt:{amount}";
    }

    public static string AlphaCaller(int amount) => SummarizeAlpha(amount);

    public static string BetaCaller(int amount) => SummarizeBeta(amount);

    public static string LegacyName() => nameof(LegacyStatus);

    public static Type? ReflectionLookup() => Type.GetType("CSharpSemantic.LegacyStatus");
}
