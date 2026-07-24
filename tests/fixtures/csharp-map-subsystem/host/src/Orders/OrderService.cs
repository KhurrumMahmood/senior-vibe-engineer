using System;

namespace CSharpMap.Orders;

public interface IOrderFormatter
{
    string Format(int id);
}

public sealed class OrderService : IOrderFormatter
{
    public string Status { get; private set; } = "ready";

    public string Create(int id)
    {
        Status = "created";
        return Normalize(Format(id));
    }

    public string Format(int id) => $"order:{id}";

    string IOrderFormatter.Format(int id) => Format(id);

    private static string Normalize(string value) => value.Trim();
}

public class BaseOrderService
{
    public virtual string Describe(int id) => $"base:{id}";
}

public sealed class SpecialOrderService : BaseOrderService
{
    public override string Describe(int id) => $"special:{id}";
}

public static class OrderCallbacks
{
    public static Func<int, string> Formatter(OrderService service) => service.Format;
}

public static class RuntimeLookup
{
    public static Type? Find() => Type.GetType("CSharpMap.Orders.OrderService");
}
