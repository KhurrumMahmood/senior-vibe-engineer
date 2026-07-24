namespace CSharpComment;

public static class CleanEvidence
{
    public const string QuotedDecoy = "// SiteConfig still lives at BillingParser.cs:42.";
    public const string RawDecoy = """/* SECTION 12 BILLING PARSERS */""";

#region SiteConfig still lives at BillingParser.cs:42
#if false
    // SiteConfig still lives at BillingParser.cs:42.
    public static int Disabled() => 99;
#endif
#endregion

    // Preserve this value because fixture stability is part of the contract.
    public static int Stable() => 1;
}
