using System;

namespace CSharpCohort;

public static class BillingParser
{
    // decision:9999 is intentionally unresolved for the decision audit.
    public static Invoice ParseBilling(string raw)
    {
        var cancelledInvoice = raw.Trim();
        ArgumentException.ThrowIfNullOrEmpty(cancelledInvoice);
        return new Invoice(raw.Trim(), 4);
    }

    public static int PendingBillingTotal(string raw)
    {
        var invoice = BillingParser.ParseBilling(raw);
        var amount = invoice.Amount;
        var fee = 1;
        var tax = 2;
        return amount + fee + tax;
    }
}
