namespace CSharpComment;

public static class CommentEvidence
{
    public const string UnicodePrefix = "café 😀";

    // SiteConfig still lives at BillingParser.cs:42.
    /* SECTION 12 BILLING PARSERS */
    /// Parse the invoice state.
    public static string Normalize(string raw) => raw.Trim();
}
