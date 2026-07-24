using System;

namespace CSharpCohortTests;

public static class Program
{
    public static void Main()
    {
        var invoice = CSharpCohort.BillingParser.ParseBilling("queued");
        if (invoice.Id != "queued") throw new InvalidOperationException("parse failed");
        var total = CSharpCohort.BillingModel.Total(
            new[] { new CSharpCohort.Invoice("a", 5), new CSharpCohort.Invoice("b", 7) }
        );
        if (total != 12) throw new InvalidOperationException("total failed");
        Console.WriteLine("csharp-lexical-tests:ok");
    }
}
