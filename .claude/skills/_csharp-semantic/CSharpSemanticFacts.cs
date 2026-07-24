using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis.Operations;

namespace EngineeringSkills.CSharpSemantic;

internal static class CSharpSemanticFacts
{
    private static readonly SymbolDisplayFormat Display = new(
        globalNamespaceStyle: SymbolDisplayGlobalNamespaceStyle.Omitted,
        typeQualificationStyle: SymbolDisplayTypeQualificationStyle.NameAndContainingTypesAndNamespaces,
        genericsOptions: SymbolDisplayGenericsOptions.IncludeTypeParameters,
        memberOptions:
            SymbolDisplayMemberOptions.IncludeContainingType
            | SymbolDisplayMemberOptions.IncludeExplicitInterface
            | SymbolDisplayMemberOptions.IncludeParameters
            | SymbolDisplayMemberOptions.IncludeType,
        parameterOptions:
            SymbolDisplayParameterOptions.IncludeType
            | SymbolDisplayParameterOptions.IncludeName
            | SymbolDisplayParameterOptions.IncludeDefaultValue,
        miscellaneousOptions:
            SymbolDisplayMiscellaneousOptions.EscapeKeywordIdentifiers
            | SymbolDisplayMiscellaneousOptions.IncludeNullableReferenceTypeModifier
            | SymbolDisplayMiscellaneousOptions.UseSpecialTypes
    );

    private static string SymbolId(ISymbol? symbol)
    {
        if (symbol is null)
        {
            return string.Empty;
        }

        return symbol.GetDocumentationCommentId()
            ?? $"{symbol.Kind}:{symbol.ToDisplayString(Display)}";
    }

    private static string Signature(ISymbol? symbol) =>
        symbol?.ToDisplayString(Display) ?? string.Empty;

    private static int Line(SyntaxNode node) =>
        node.GetLocation().GetLineSpan().StartLinePosition.Line + 1;

    private static Dictionary<string, object?> Caller(
        SemanticModel model,
        SyntaxNode node
    )
    {
        var symbol = model.GetEnclosingSymbol(node.SpanStart) as IMethodSymbol;
        return new Dictionary<string, object?>
        {
            ["symbol_id"] = SymbolId(symbol),
            ["signature"] = Signature(symbol),
        };
    }

    private static List<Dictionary<string, object?>> Parameters(IMethodSymbol symbol) =>
        symbol.Parameters
            .Select(
                parameter => new Dictionary<string, object?>
                {
                    ["name"] = parameter.Name,
                    ["type"] = Signature(parameter.Type),
                    ["has_explicit_default"] = parameter.HasExplicitDefaultValue,
                    ["default_value"] = parameter.HasExplicitDefaultValue
                        ? parameter.ExplicitDefaultValue
                        : null,
                    ["is_params"] = parameter.IsParams,
                    ["ref_kind"] = parameter.RefKind.ToString(),
                }
            )
            .ToList();

    private static bool IsPartial(SyntaxNode declaration, ISymbol symbol)
    {
        static bool HasPartial(SyntaxNode node) =>
            node switch
            {
                TypeDeclarationSyntax type => type.Modifiers.Any(SyntaxKind.PartialKeyword),
                MethodDeclarationSyntax method => method.Modifiers.Any(SyntaxKind.PartialKeyword),
                _ => false,
            };

        return HasPartial(declaration)
            || symbol.ContainingType?.DeclaringSyntaxReferences.Any(
                reference => HasPartial(reference.GetSyntax())
            ) == true;
    }

    private static string? Literal(IOperation? operation)
    {
        if (operation is null || !operation.ConstantValue.HasValue)
        {
            return null;
        }

        return operation.ConstantValue.Value as string;
    }

    private static ISymbol? AssignedSymbol(IOperation operation) =>
        operation switch
        {
            IPropertyReferenceOperation property => property.Property,
            IFieldReferenceOperation field => field.Field,
            _ => null,
        };

    private static string ReferenceContext(SimpleNameSyntax node, ISymbol symbol)
    {
        if (
            node.Ancestors().OfType<InvocationExpressionSyntax>().Any(
                invocation => invocation.Expression is IdentifierNameSyntax identifier
                    && identifier.Identifier.ValueText == "nameof"
            )
        )
        {
            return "nameof";
        }

        var invocation = node.Ancestors().OfType<InvocationExpressionSyntax>().FirstOrDefault();
        if (invocation is not null && invocation.Expression.Span.Contains(node.Span))
        {
            return "direct_call";
        }

        return symbol is IMethodSymbol ? "method_group_or_value" : "symbol_reference";
    }

    private static Dictionary<string, object?> CallRow(
        string path,
        string role,
        SemanticModel model,
        SyntaxNode syntax,
        IMethodSymbol? target,
        IEnumerable<IArgumentOperation> arguments,
        string targetKind,
        string source
    )
    {
        return new Dictionary<string, object?>
        {
            ["path"] = path,
            ["role"] = role,
            ["line"] = Line(syntax),
            ["source"] = source,
            ["target_kind"] = targetKind,
            ["target_symbol_id"] = SymbolId(target),
            ["target_signature"] = Signature(target),
            ["target_parameters"] = target is null
                ? new List<Dictionary<string, object?>>()
                : Parameters(target),
            ["arguments"] = arguments
                .Select(
                    argument => new Dictionary<string, object?>
                    {
                        ["parameter_name"] = argument.Parameter?.Name,
                        ["source"] = argument.Syntax.ToString(),
                        ["is_named"] = argument.Syntax is ArgumentSyntax named
                            && named.NameColon is not null,
                        ["argument_kind"] = argument.ArgumentKind.ToString(),
                    }
                )
                .ToList(),
            ["caller"] = Caller(model, syntax),
            ["resolved"] = target is not null,
        };
    }

    public static int Main(string[] args)
    {
        if (args.Length < 2)
        {
            Console.Error.WriteLine("usage: <reference-dir> <role=absolute.cs>...");
            return 2;
        }

        var referenceDirectory = Path.GetFullPath(args[0]);
        var inputs = new List<(string Role, string Path)>();
        foreach (var raw in args.Skip(1))
        {
            var separator = raw.IndexOf('=');
            if (separator <= 0 || separator == raw.Length - 1)
            {
                Console.Error.WriteLine($"invalid input descriptor: {raw}");
                return 2;
            }

            inputs.Add((raw[..separator], Path.GetFullPath(raw[(separator + 1)..])));
        }

        var selected = inputs.Where(input => input.Role is "source" or "test").ToList();
        var parseOptions = new CSharpParseOptions(
            LanguageVersion.CSharp14,
            DocumentationMode.Parse,
            SourceCodeKind.Regular
        );
        var trees = selected
            .Select(
                input => CSharpSyntaxTree.ParseText(
                    File.ReadAllText(input.Path),
                    parseOptions,
                    input.Path
                )
            )
            .ToList();
        var roles = selected.ToDictionary(input => input.Path, input => input.Role);
        var references = Directory.GetFiles(referenceDirectory, "*.dll")
            .OrderBy(path => path, StringComparer.Ordinal)
            .Select(path => MetadataReference.CreateFromFile(path))
            .ToList();
        var compilation = CSharpCompilation.Create(
            "EngineeringSkills.CSharpSemantic.Analysis",
            trees,
            references,
            new CSharpCompilationOptions(
                OutputKind.DynamicallyLinkedLibrary,
                deterministic: true,
                nullableContextOptions: NullableContextOptions.Enable
            )
        );

        var declarations = new List<Dictionary<string, object?>>();
        var calls = new List<Dictionary<string, object?>>();
        var referencesFound = new List<Dictionary<string, object?>>();
        var writes = new List<Dictionary<string, object?>>();
        var boundaries = new List<Dictionary<string, object?>>();

        foreach (var tree in trees.OrderBy(tree => tree.FilePath, StringComparer.Ordinal))
        {
            var path = Path.GetFullPath(tree.FilePath);
            var role = roles[path];
            var model = compilation.GetSemanticModel(tree, ignoreAccessibility: false);
            var root = tree.GetRoot();

            foreach (var declaration in root.DescendantNodes().OfType<BaseTypeDeclarationSyntax>())
            {
                var symbol = model.GetDeclaredSymbol(declaration);
                if (symbol is null)
                {
                    continue;
                }

                var kind = declaration switch
                {
                    EnumDeclarationSyntax => "enum",
                    InterfaceDeclarationSyntax => "interface",
                    RecordDeclarationSyntax => "record",
                    StructDeclarationSyntax => "struct",
                    _ => "class",
                };
                var partial = IsPartial(declaration, symbol);
                declarations.Add(
                    new Dictionary<string, object?>
                    {
                        ["path"] = path,
                        ["role"] = role,
                        ["line"] = Line(declaration),
                        ["kind"] = kind,
                        ["name"] = symbol.Name,
                        ["containing_type"] = Signature(symbol.ContainingType),
                        ["symbol_id"] = SymbolId(symbol),
                        ["signature"] = Signature(symbol),
                        ["accessibility"] = symbol.DeclaredAccessibility.ToString(),
                        ["partial"] = partial,
                    }
                );
                if (partial)
                {
                    boundaries.Add(
                        new Dictionary<string, object?>
                        {
                            ["kind"] = "partial_declaration",
                            ["path"] = path,
                            ["line"] = Line(declaration),
                            ["symbol_id"] = SymbolId(symbol),
                        }
                    );
                }
            }

            foreach (var declaration in root.DescendantNodes().OfType<MethodDeclarationSyntax>())
            {
                var symbol = model.GetDeclaredSymbol(declaration);
                if (symbol is null)
                {
                    continue;
                }

                var body = declaration.Body?.ToString()
                    ?? declaration.ExpressionBody?.Expression.ToString();
                var partial = IsPartial(declaration, symbol);
                declarations.Add(
                    new Dictionary<string, object?>
                    {
                        ["path"] = path,
                        ["role"] = role,
                        ["line"] = Line(declaration),
                        ["kind"] = "method",
                        ["name"] = symbol.Name,
                        ["containing_type"] = Signature(symbol.ContainingType),
                        ["symbol_id"] = SymbolId(symbol),
                        ["signature"] = Signature(symbol),
                        ["accessibility"] = symbol.DeclaredAccessibility.ToString(),
                        ["parameters"] = Parameters(symbol),
                        ["return_type"] = Signature(symbol.ReturnType),
                        ["body_source"] = body,
                        ["override"] = symbol.IsOverride,
                        ["overridden_symbol_id"] = SymbolId(symbol.OverriddenMethod),
                        ["explicit_interface_implementations"] = symbol
                            .ExplicitInterfaceImplementations.Select(SymbolId).ToList(),
                        ["partial"] = partial,
                    }
                );
                if (symbol.IsOverride || symbol.ExplicitInterfaceImplementations.Length > 0)
                {
                    boundaries.Add(
                        new Dictionary<string, object?>
                        {
                            ["kind"] = symbol.IsOverride
                                ? "override_dispatch"
                                : "explicit_interface_dispatch",
                            ["path"] = path,
                            ["line"] = Line(declaration),
                            ["symbol_id"] = SymbolId(symbol),
                        }
                    );
                }
            }

            foreach (var declaration in root.DescendantNodes().OfType<PropertyDeclarationSyntax>())
            {
                var symbol = model.GetDeclaredSymbol(declaration);
                if (symbol is null)
                {
                    continue;
                }

                var initializerOperation = declaration.Initializer is null
                    ? null
                    : model.GetOperation(declaration.Initializer.Value);
                declarations.Add(
                    new Dictionary<string, object?>
                    {
                        ["path"] = path,
                        ["role"] = role,
                        ["line"] = Line(declaration),
                        ["kind"] = "property",
                        ["name"] = symbol.Name,
                        ["symbol_id"] = SymbolId(symbol),
                        ["signature"] = Signature(symbol),
                        ["accessibility"] = symbol.DeclaredAccessibility.ToString(),
                        ["type"] = Signature(symbol.Type),
                        ["initializer_source"] = declaration.Initializer?.Value.ToString(),
                        ["initializer_string_literal"] = Literal(initializerOperation),
                        ["override"] = symbol.IsOverride,
                    }
                );
            }

            foreach (var invocation in root.DescendantNodes().OfType<InvocationExpressionSyntax>())
            {
                var operation = model.GetOperation(invocation);
                if (operation is IInvocationOperation direct)
                {
                    calls.Add(
                        CallRow(
                            path,
                            role,
                            model,
                            invocation,
                            direct.TargetMethod,
                            direct.Arguments,
                            "callable",
                            invocation.ToString()
                        )
                    );
                    var containing = direct.TargetMethod.ContainingType?.ToDisplayString();
                    if (
                        containing is "System.Type" or "System.Reflection.MethodInfo"
                        || direct.TargetMethod.ContainingNamespace.ToDisplayString().StartsWith(
                            "System.Reflection",
                            StringComparison.Ordinal
                        )
                    )
                    {
                        boundaries.Add(
                            new Dictionary<string, object?>
                            {
                                ["kind"] = "reflection_or_runtime_name_lookup",
                                ["path"] = path,
                                ["line"] = Line(invocation),
                                ["target_signature"] = Signature(direct.TargetMethod),
                            }
                        );
                    }
                }
                else if (operation is IDynamicInvocationOperation)
                {
                    calls.Add(
                        CallRow(
                            path,
                            role,
                            model,
                            invocation,
                            null,
                            Array.Empty<IArgumentOperation>(),
                            "dynamic",
                            invocation.ToString()
                        )
                    );
                    boundaries.Add(
                        new Dictionary<string, object?>
                        {
                            ["kind"] = "dynamic_dispatch",
                            ["path"] = path,
                            ["line"] = Line(invocation),
                        }
                    );
                }
            }

            foreach (
                var creation in root.DescendantNodes().OfType<BaseObjectCreationExpressionSyntax>()
            )
            {
                if (model.GetOperation(creation) is not IObjectCreationOperation operation)
                {
                    continue;
                }

                calls.Add(
                    CallRow(
                        path,
                        role,
                        model,
                        creation,
                        operation.Constructor,
                        operation.Arguments,
                        "constructor",
                        creation.ToString()
                    )
                );
            }

            foreach (var reference in root.DescendantNodes().OfType<SimpleNameSyntax>())
            {
                var info = model.GetSymbolInfo(reference);
                var symbol = info.Symbol;
                referencesFound.Add(
                    new Dictionary<string, object?>
                    {
                        ["path"] = path,
                        ["role"] = role,
                        ["line"] = Line(reference),
                        ["source"] = reference.Identifier.ValueText,
                        ["target_symbol_id"] = SymbolId(symbol),
                        ["target_signature"] = Signature(symbol),
                        ["context"] = symbol is null
                            ? "unresolved"
                            : ReferenceContext(reference, symbol),
                        ["candidate_signatures"] = info.CandidateSymbols
                            .Select(Signature).OrderBy(value => value, StringComparer.Ordinal).ToList(),
                        ["resolved"] = symbol is not null,
                    }
                );
                if (symbol is IMethodSymbol && ReferenceContext(reference, symbol) == "method_group_or_value")
                {
                    boundaries.Add(
                        new Dictionary<string, object?>
                        {
                            ["kind"] = "delegate_or_method_group",
                            ["path"] = path,
                            ["line"] = Line(reference),
                            ["target_symbol_id"] = SymbolId(symbol),
                        }
                    );
                }
            }

            foreach (var assignment in root.DescendantNodes().OfType<AssignmentExpressionSyntax>())
            {
                if (model.GetOperation(assignment) is not IAssignmentOperation operation)
                {
                    continue;
                }

                var target = AssignedSymbol(operation.Target);
                writes.Add(
                    new Dictionary<string, object?>
                    {
                        ["path"] = path,
                        ["role"] = role,
                        ["line"] = Line(assignment),
                        ["source"] = assignment.ToString(),
                        ["target_symbol_id"] = SymbolId(target),
                        ["target_signature"] = Signature(target),
                        ["operator"] = assignment.OperatorToken.ValueText,
                        ["value_source"] = assignment.Right.ToString(),
                        ["string_literal"] = Literal(operation.Value),
                        ["caller"] = Caller(model, assignment),
                        ["resolved"] = target is not null,
                    }
                );
            }
        }

        foreach (
            var group in declarations
                .Where(row => Equals(row["kind"], "method"))
                .GroupBy(
                    row => $"{row["name"]}:{row["containing_type"]}",
                    StringComparer.Ordinal
                )
                .Where(group => group.Count() > 1)
        )
        {
            boundaries.Add(
                new Dictionary<string, object?>
                {
                    ["kind"] = "overload_set",
                    ["name"] = group.First()["name"],
                    ["signatures"] = group.Select(row => row["signature"]).ToList(),
                }
            );
        }

        foreach (var excluded in inputs.Where(input => input.Role is "generated" or "vendor"))
        {
            boundaries.Add(
                new Dictionary<string, object?>
                {
                    ["kind"] = excluded.Role == "generated"
                        ? "excluded_generated_input"
                        : "excluded_vendor_input",
                    ["path"] = excluded.Path,
                }
            );
        }

        var diagnostics = compilation.GetDiagnostics()
            .Where(diagnostic => diagnostic.Severity >= DiagnosticSeverity.Warning)
            .Select(
                diagnostic => new Dictionary<string, object?>
                {
                    ["id"] = diagnostic.Id,
                    ["severity"] = diagnostic.Severity.ToString(),
                    ["message"] = diagnostic.GetMessage(),
                    ["path"] = diagnostic.Location.IsInSource
                        ? diagnostic.Location.SourceTree?.FilePath
                        : null,
                    ["line"] = diagnostic.Location.IsInSource
                        ? diagnostic.Location.GetLineSpan().StartLinePosition.Line + 1
                        : null,
                }
            )
            .ToList();

        var payload = new Dictionary<string, object?>
        {
            ["schema_version"] = 1,
            ["roslyn_assembly"] = typeof(CSharpCompilation).Assembly.FullName,
            ["code_analysis_assembly"] = typeof(Compilation).Assembly.FullName,
            ["declarations"] = declarations,
            ["calls"] = calls,
            ["references"] = referencesFound,
            ["writes"] = writes,
            ["boundaries"] = boundaries,
            ["diagnostics"] = diagnostics,
        };
        Console.WriteLine(
            JsonSerializer.Serialize(
                payload,
                new JsonSerializerOptions { WriteIndented = false }
            )
        );
        return 0;
    }
}
