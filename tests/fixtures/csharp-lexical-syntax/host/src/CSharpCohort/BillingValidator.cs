namespace CSharpCohort;

public static class BillingValidator
{
    public static bool ValidateBilling(Invoice invoice) => invoice.Amount >= 0;
}
