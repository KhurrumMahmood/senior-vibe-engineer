using System;

namespace CSharpMovePilot;

internal static class MoveTests
{
    internal static int Run()
    {
        Invoice invoice = new("INV-42", 125m);
        if (invoice.Render() != "invoice:INV-42:125:csharp-move")
        {
            throw new InvalidOperationException("invoice rendering changed");
        }

        Console.WriteLine("csharp-move-tests:ok");
        return 0;
    }
}
