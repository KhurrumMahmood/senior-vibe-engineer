using System;

namespace CSharpSemantic;

public static class Smoke
{
    public static void Main()
    {
        var processor = new Processor();
        var job = new Job();
        Console.WriteLine(
            $"{SemanticCases.AlphaCaller(7)}:{SemanticCases.BetaCaller(8)}:{job.Status}"
        );
        _ = processor.Process(7);
        _ = processor.Process("seven");
        _ = new OverrideFormatter().Format(7);
        _ = LegacyStatus.Queued;
        _ = CanonicalStatus.Queued;
    }
}
