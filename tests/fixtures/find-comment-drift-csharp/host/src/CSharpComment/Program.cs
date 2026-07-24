using System;

namespace CSharpComment;

public static class Program
{
    public static void Main()
    {
        var value = CommentEvidence.Normalize(" queued ");
        Console.WriteLine($"csharp-comment:{value}:{CleanEvidence.Stable()}");
    }
}
