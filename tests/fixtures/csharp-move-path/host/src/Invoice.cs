namespace CSharpMovePilot;

internal sealed record Invoice(string Id, decimal Amount)
{
    internal string Render() => $"invoice:{Id}:{Amount:0}:csharp-move";
}
