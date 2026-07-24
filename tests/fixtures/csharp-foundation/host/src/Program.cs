using System;

namespace CSharpFoundation;

internal static class Program
{
    private static int Main(string[] args)
    {
        if (args is ["--self-test"])
        {
            return FoundationTests.Run();
        }

        Console.WriteLine(new Invoice("INV-42", 125m).Render());
        return 0;
    }
}
