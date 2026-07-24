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
        if (CSharpCohort.DomainOperations.LoadExports() != 5)
            throw new InvalidOperationException("load exports failed");
        if (CSharpCohort.DomainOperations.SaveExports() != 6)
            throw new InvalidOperationException("save exports failed");
        if (CSharpCohort.DomainOperations.RenderExports() != 9)
            throw new InvalidOperationException("render exports failed");
        Console.WriteLine("csharp-lexical-tests:ok");
    }
}
