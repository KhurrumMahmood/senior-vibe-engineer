using System;

namespace CSharpCohort;

public static class Program
{
    public static void Main()
    {
        var invoice = BillingParser.ParseBilling("queued");
        var amount = BillingModel.Total(new[] { invoice, new Invoice("extra", 8) });
        Console.WriteLine($"csharp-lexical:{amount}:{invoice.Id}");
    }
}
