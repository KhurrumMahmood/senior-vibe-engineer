namespace CSharpCohort;

public static class Syntax
{
    public static Invoice HandledParse(string raw)
    {
        if (!string.IsNullOrWhiteSpace(raw))
        {
            return BillingParser.ParseBilling(raw);
        }

        return new Invoice("empty", 0);
    }

    public static Invoice UnhandledParse(string raw) => BillingParser.ParseBilling(raw);

    public static int RouteInvoice(int value)
    {
        var score = 0;
        if (value > 0) score++;
        if (value > 1) score++;
        if (value > 2) score++;
        if (value > 3) score++;
        if (value > 4) score++;
        if (value > 5) score++;
        if (value > 6) score++;
        if (value > 7) score++;
        return score;
    }
}
