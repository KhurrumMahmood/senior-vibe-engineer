using System.Collections.Generic;
using System.Linq;

namespace CSharpCohort;

// decision:0001 keeps the source-only C# boundary explicit.
public sealed record Invoice(string Id, int Amount);

public abstract record BillingOutcome
{
    public sealed record Accepted(Invoice Invoice) : BillingOutcome;
    public sealed record Rejected(string Reason) : BillingOutcome;
}

public static class BillingModel
{
    public static string Label(this Invoice invoice) => $"{invoice.Id}:{invoice.Amount}";

    public static int Total(Invoice invoice) => invoice.Amount;

    public static int Total(IReadOnlyList<Invoice> invoices) =>
        invoices.Sum(invoice => invoice.Amount);
}
