using System;

namespace CSharpCommentTests;

public static class Program
{
    // SiteConfig still lives at BillingParser.cs:42.
    public static void Main()
    {
        if (CSharpComment.CommentEvidence.Normalize(" queued ") != "queued")
        {
            throw new InvalidOperationException("normalization failed");
        }

        Console.WriteLine("csharp-comment-tests:ok");
    }
}
