using System;
using CSharpMap.Orders;

namespace CSharpMap;

public static class Program
{
    public static int Main()
    {
        var service = new OrderService();
        Console.WriteLine(service.Create(7));
        return 0;
    }
}
