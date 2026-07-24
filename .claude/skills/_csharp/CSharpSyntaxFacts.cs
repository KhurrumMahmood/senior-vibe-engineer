using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

internal static class CSharpSyntaxFacts
{
    private static int Line(SyntaxTree tree, SyntaxNodeOrToken item) =>
        tree.GetLineSpan(item.Span).StartLinePosition.Line + 1;

    private static int Line(SyntaxTree tree, SyntaxTrivia item) =>
        tree.GetLineSpan(item.Span).StartLinePosition.Line + 1;

    private static int EndLine(SyntaxTree tree, SyntaxNode item) =>
        tree.GetLineSpan(item.Span).EndLinePosition.Line + 1;

    private static string Namespace(SyntaxNode node)
    {
        var names = node.Ancestors()
            .OfType<BaseNamespaceDeclarationSyntax>()
            .Select(item => item.Name.ToString())
            .Reverse();
        return string.Join(".", names);
    }

    private static string TypePath(SyntaxNode node)
    {
        var names = node.Ancestors()
            .OfType<BaseTypeDeclarationSyntax>()
            .Select(item => item.Identifier.ValueText)
            .Reverse();
        return string.Join(".", names);
    }

    private static string Qualified(SyntaxNode node, string name)
    {
        var parts = new[] { Namespace(node), TypePath(node), name }
            .Where(item => !string.IsNullOrEmpty(item));
        return string.Join(".", parts);
    }

    private static string Compact(SyntaxNode node) =>
        string.Join(" ", node.DescendantTokens().Select(token => token.Text));

    private static string TypeKind(BaseTypeDeclarationSyntax declaration) => declaration switch
    {
        RecordDeclarationSyntax record when record.ClassOrStructKeyword.IsKind(SyntaxKind.StructKeyword) => "record-struct",
        RecordDeclarationSyntax => "record-class",
        ClassDeclarationSyntax => "class",
        InterfaceDeclarationSyntax => "interface",
        StructDeclarationSyntax => "struct",
        EnumDeclarationSyntax => "enum",
        _ => "type",
    };

    private static object TypeDeclaration(SyntaxTree tree, BaseTypeDeclarationSyntax declaration) => new
    {
        kind = TypeKind(declaration),
        name = declaration.Identifier.ValueText,
        qualified_name = Qualified(declaration, declaration.Identifier.ValueText),
        signature = string.Join(" ", declaration.Modifiers.Select(item => item.ValueText)
            .Append(TypeKind(declaration)).Append(declaration.Identifier.ValueText)),
        line = Line(tree, declaration),
        end_line = EndLine(tree, declaration),
        modifiers = declaration.Modifiers.Select(item => item.ValueText).ToArray(),
        extension_receiver = (string?)null,
    };

    private static string MethodSignature(MethodDeclarationSyntax method) =>
        $"{Compact(method.ReturnType)} {Qualified(method, method.Identifier.ValueText)}" +
        $"{(method.TypeParameterList is null ? "" : Compact(method.TypeParameterList))}" +
        $"({string.Join(", ", method.ParameterList.Parameters.Select(item => Compact(item)))})";

    private static object MethodDeclaration(SyntaxTree tree, MethodDeclarationSyntax method) => new
    {
        kind = "method",
        name = method.Identifier.ValueText,
        qualified_name = Qualified(method, method.Identifier.ValueText),
        signature = MethodSignature(method),
        line = Line(tree, method),
        end_line = EndLine(tree, method),
        modifiers = method.Modifiers.Select(item => item.ValueText).ToArray(),
        extension_receiver = method.ParameterList.Parameters.FirstOrDefault()
            is ParameterSyntax first && first.Modifiers.Any(SyntaxKind.ThisKeyword)
                ? first.Type?.ToString()
                : null,
    };

    private static object PropertyDeclaration(SyntaxTree tree, PropertyDeclarationSyntax property) => new
    {
        kind = "property",
        name = property.Identifier.ValueText,
        qualified_name = Qualified(property, property.Identifier.ValueText),
        signature = $"{Compact(property.Type)} {Qualified(property, property.Identifier.ValueText)}",
        line = Line(tree, property),
        end_line = EndLine(tree, property),
        modifiers = property.Modifiers.Select(item => item.ValueText).ToArray(),
        extension_receiver = (string?)null,
    };

    private static string InvocationSpelling(InvocationExpressionSyntax invocation) =>
        invocation.Expression switch
        {
            IdentifierNameSyntax identifier => identifier.Identifier.ValueText,
            GenericNameSyntax generic => generic.Identifier.ValueText,
            MemberAccessExpressionSyntax member when member.Name is SimpleNameSyntax name => name.Identifier.ValueText,
            MemberBindingExpressionSyntax binding => binding.Name.Identifier.ValueText,
            _ => invocation.Expression.ToString(),
        };

    private static object Invocation(SyntaxTree tree, InvocationExpressionSyntax invocation) => new
    {
        spelling = InvocationSpelling(invocation),
        source = invocation.Expression.ToString(),
        line = Line(tree, invocation),
        span = new { start = invocation.Span.Start, end = invocation.Span.End },
        enclosures = invocation.Ancestors()
            .TakeWhile(item => item is not MethodDeclarationSyntax)
            .OfType<IfStatementSyntax>()
            .Select(_ => "if")
            .ToArray(),
    };

    private static int BranchScore(SyntaxNode body) =>
        body.DescendantNodesAndSelf().Count(node => node is
            IfStatementSyntax or SwitchSectionSyntax or SwitchExpressionArmSyntax or
            ForStatementSyntax or ForEachStatementSyntax or WhileStatementSyntax or
            DoStatementSyntax or CatchClauseSyntax or ConditionalExpressionSyntax) +
        body.DescendantNodesAndSelf().OfType<BinaryExpressionSyntax>().Count(binary =>
            binary.IsKind(SyntaxKind.LogicalAndExpression) ||
            binary.IsKind(SyntaxKind.LogicalOrExpression) ||
            binary.IsKind(SyntaxKind.CoalesceExpression));

    private static object Function(SyntaxTree tree, string path, MethodDeclarationSyntax method)
    {
        SyntaxNode? body = method.Body ?? (SyntaxNode?)method.ExpressionBody?.Expression;
        var bodyText = body?.ToFullString() ?? "";
        return new
        {
            file = path,
            name = method.Identifier.ValueText,
            qualified_name = Qualified(method, method.Identifier.ValueText),
            signature = MethodSignature(method),
            line = Line(tree, method),
            end_line = EndLine(tree, method),
            loc = EndLine(tree, method) - Line(tree, method) + 1,
            body = bodyText,
            normalized_body = body is null
                ? ""
                : string.Join("\u001f", body.DescendantTokens().Select(token => token.Text)),
            spelling = method.ToFullString(),
            branch_score = body is null ? 0 : BranchScore(body),
            calls = body is null
                ? Array.Empty<object>()
                : body.DescendantNodesAndSelf().OfType<InvocationExpressionSyntax>()
                    .Select(invocation => Invocation(tree, invocation)).ToArray(),
        };
    }

    private static string CommentForm(SyntaxTrivia trivia) => trivia.Kind() switch
    {
        SyntaxKind.SingleLineCommentTrivia => "line",
        SyntaxKind.MultiLineCommentTrivia => "block",
        SyntaxKind.SingleLineDocumentationCommentTrivia => "documentation-line",
        SyntaxKind.MultiLineDocumentationCommentTrivia => "documentation-block",
        _ => "comment",
    };

    private static string CommentText(SyntaxTrivia trivia)
    {
        var text = trivia.ToFullString();
        if (trivia.IsKind(SyntaxKind.SingleLineCommentTrivia)) return text[2..];
        if (trivia.IsKind(SyntaxKind.MultiLineCommentTrivia) && text.Length >= 4) return text[2..^2];
        return text;
    }

    private static object Analyze(string path)
    {
        var source = File.ReadAllText(path);
        var options = CSharpParseOptions.Default
            .WithLanguageVersion(LanguageVersion.CSharp14)
            .WithDocumentationMode(DocumentationMode.Parse);
        var tree = CSharpSyntaxTree.ParseText(source, options, path);
        var root = tree.GetCompilationUnitRoot();
        var declarations = new List<object>();
        declarations.AddRange(root.DescendantNodes().OfType<BaseTypeDeclarationSyntax>()
            .Select(item => TypeDeclaration(tree, item)));
        declarations.AddRange(root.DescendantNodes().OfType<MethodDeclarationSyntax>()
            .Select(item => MethodDeclaration(tree, item)));
        declarations.AddRange(root.DescendantNodes().OfType<PropertyDeclarationSyntax>()
            .Select(item => PropertyDeclaration(tree, item)));
        var comments = root.DescendantTrivia(descendIntoTrivia: true)
            .Where(item => item.IsKind(SyntaxKind.SingleLineCommentTrivia) ||
                           item.IsKind(SyntaxKind.MultiLineCommentTrivia) ||
                           item.IsKind(SyntaxKind.SingleLineDocumentationCommentTrivia) ||
                           item.IsKind(SyntaxKind.MultiLineDocumentationCommentTrivia))
            .Select(item => new
            {
                form = CommentForm(item),
                text = CommentText(item),
                line = Line(tree, item),
                span = new { start = item.Span.Start, end = item.Span.End },
            }).ToArray();
        var identifiers = root.DescendantTokens()
            .Where(token => token.IsKind(SyntaxKind.IdentifierToken))
            .Select(token => new
            {
                text = token.ValueText,
                line = Line(tree, token),
                span = new { start = token.Span.Start, end = token.Span.End },
            }).ToArray();
        var diagnostics = tree.GetDiagnostics()
            .Where(item => item.Severity == DiagnosticSeverity.Error)
            .Select(item => new { id = item.Id, message = item.GetMessage() }).ToArray();
        return new
        {
            path,
            @namespace = root.Members.OfType<BaseNamespaceDeclarationSyntax>()
                .Select(item => item.Name.ToString()).FirstOrDefault() ?? "",
            usings = root.Usings.Select(item => item.Name?.ToString() ?? "").ToArray(),
            declarations = declarations.OrderBy(item => JsonSerializer.Serialize(item)).ToArray(),
            functions = root.DescendantNodes().OfType<MethodDeclarationSyntax>()
                .Select(item => Function(tree, path, item)).ToArray(),
            comments,
            identifier_tokens = identifiers,
            diagnostics,
        };
    }

    public static int Main(string[] args)
    {
        var files = args.Select(Analyze).ToArray();
        Console.WriteLine(JsonSerializer.Serialize(new { schema_version = 1, files }));
        return 0;
    }
}
