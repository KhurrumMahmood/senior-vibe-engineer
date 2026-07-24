using System;

namespace CSharpFoundation;

internal static class FoundationTests
{
    internal static int Run()
    {
        Invoice invoice = new("INV-42", 125m);
        if (invoice.Render() != "invoice:INV-42:125:csharp")
        {
            throw new InvalidOperationException("invoice rendering changed");
        }

        Console.WriteLine("csharp-foundation-tests:ok");
        return 0;
    }
}
