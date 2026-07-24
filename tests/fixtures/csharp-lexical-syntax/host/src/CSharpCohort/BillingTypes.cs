namespace CSharpCohort;

public static class BillingTypes
{
    public static int QueuedBillingTotal(string raw)
    {
        var invoice = BillingParser.ParseBilling(raw);
        var amount = invoice.Amount;
        var fee = 1;
        var tax = 2;
        return amount + fee + tax;
    }
}
