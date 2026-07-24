using System;

namespace CSharpSemantic;

public static class SemanticTests
{
    public static void Main()
    {
        var job = new Job();
        job.Start();
        job.Complete();
        if (job.Status != JobStatus.Done)
        {
            throw new InvalidOperationException("state fixture failed");
        }

        if (!SemanticCases.AlphaCaller(4).Equals("receipt:4", StringComparison.Ordinal))
        {
            throw new InvalidOperationException("semantic fixture failed");
        }

        Console.WriteLine("csharp-semantic-native-test:ok");
    }
}
