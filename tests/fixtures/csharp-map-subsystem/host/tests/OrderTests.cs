using System;
using CSharpMap.Orders;

namespace CSharpMap;

public static class OrderTests
{
    public static int Main()
    {
        var service = new OrderService();
        if (service.Create(8) != "order:8" || service.Status != "created")
        {
            return 1;
        }

        Console.WriteLine("csharp-map-native-test:ok");
        return 0;
    }
}
