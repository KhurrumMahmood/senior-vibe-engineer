import 'dart:convert';
import 'dart:io';

import 'package:analyzer/dart/analysis/utilities.dart';
import 'package:analyzer/dart/ast/ast.dart';
import 'package:analyzer/dart/ast/token.dart';
import 'package:analyzer/dart/ast/visitor.dart';

Never _fail(String message) {
  stderr.writeln('[dart_syntax_facts] $message');
  exit(2);
}

String _form(String lexeme) {
  if (lexeme.startsWith('///') || lexeme.startsWith('/**')) return 'doc';
  if (lexeme.startsWith('//')) return 'line';
  return 'block';
}

List<Map<String, Object?>> _comments(CompilationUnit unit) {
  final seen = <int>{};
  final rows = <Map<String, Object?>>[];
  Token? token = unit.beginToken;
  while (token != null) {
    CommentToken? comment = token.precedingComments;
    while (comment != null) {
      if (seen.add(comment.offset)) {
        final location = unit.lineInfo.getLocation(comment.offset);
        rows.add({
          'text': comment.lexeme,
          'form': _form(comment.lexeme),
          'offset': comment.offset,
          'end': comment.end,
          'line': location.lineNumber,
          'column': location.columnNumber,
        });
      }
      comment = comment.next as CommentToken?;
    }
    if (token.isEof) break;
    token = token.next;
  }
  rows.sort(
    (left, right) => (left['offset'] as int).compareTo(right['offset'] as int),
  );
  return rows;
}

num? _numeric(Expression expression) {
  Expression current = expression;
  while (current is ParenthesizedExpression) {
    current = current.expression;
  }
  if (current is IntegerLiteral) return current.value;
  if (current is DoubleLiteral) return current.value;
  return null;
}

num? _fixedReturn(FunctionBody body) {
  if (body is ExpressionFunctionBody) return _numeric(body.expression);
  if (body is! BlockFunctionBody || body.block.statements.length != 1)
    return null;
  final statement = body.block.statements.single;
  if (statement is! ReturnStatement || statement.expression == null)
    return null;
  return _numeric(statement.expression!);
}

Map<String, Object?>? _functionFact(
  AnnotatedNode node,
  String name,
  FunctionBody body,
  CompilationUnit unit,
  String content,
) {
  final comment = node.documentationComment;
  if (comment == null ||
      !comment.tokens.every((token) => token.lexeme.startsWith('///'))) {
    return null;
  }
  final declarationOffset = node.firstTokenAfterCommentAndMetadata.offset;
  final gap = content.substring(comment.end, declarationOffset);
  if ('\n'.allMatches(gap).length > 1) return null;
  final value = _fixedReturn(body);
  if (value == null) return null;
  final text = comment.tokens.map((token) => token.lexeme).join('\n');
  final begin = comment.beginToken.offset;
  return {
    'name': name,
    'line': unit.lineInfo.getLocation(declarationOffset).lineNumber,
    'offset': declarationOffset,
    'end': node.end,
    'comment': text,
    'comment_line': unit.lineInfo.getLocation(begin).lineNumber,
    'comment_offset': begin,
    'comment_end': comment.end,
    'fixed_return': value,
  };
}

bool _insideTryBody(MethodInvocation node) {
  AstNode? child = node;
  AstNode? parent = node.parent;
  while (parent != null) {
    if (parent is FunctionBody) return false;
    if (parent is TryStatement && identical(child, parent.body)) return true;
    child = parent;
    parent = parent.parent;
  }
  return false;
}

class _FactsVisitor extends RecursiveAstVisitor<void> {
  _FactsVisitor(this.unit, this.content);

  final CompilationUnit unit;
  final String content;
  final List<Map<String, Object?>> functions = [];
  final List<Map<String, Object?>> calls = [];

  @override
  void visitFunctionDeclaration(FunctionDeclaration node) {
    if (node.parent is CompilationUnit && !node.isGetter && !node.isSetter) {
      final fact = _functionFact(
        node,
        node.name.lexeme,
        node.functionExpression.body,
        unit,
        content,
      );
      if (fact != null) functions.add(fact);
    }
    super.visitFunctionDeclaration(node);
  }

  @override
  void visitMethodInvocation(MethodInvocation node) {
    if (node.target == null && !node.isCascaded) {
      final location = unit.lineInfo.getLocation(node.offset);
      calls.add({
        'spelling': node.methodName.name,
        'line': location.lineNumber,
        'column': location.columnNumber,
        'offset': node.offset,
        'end': node.end,
        'in_try': _insideTryBody(node),
      });
    }
    super.visitMethodInvocation(node);
  }
}

Map<String, Object?> _analyze(String root, String rawPath) {
  final rootUri = Directory(root).absolute.uri;
  final file = File(rawPath).absolute;
  if (!file.uri.toString().startsWith(rootUri.toString())) {
    _fail('source escapes project root: ${file.path}');
  }
  final content = file.readAsStringSync();
  final result = parseString(
    content: content,
    path: file.path,
    throwIfDiagnostics: false,
  );
  final diagnostics = result.errors
      .map(
        (error) => {
          'code': error.diagnosticCode.lowerCaseName,
          'message': error.message,
          'offset': error.offset,
          'length': error.length,
          'line': result.unit.lineInfo.getLocation(error.offset).lineNumber,
        },
      )
      .toList();
  final visitor = _FactsVisitor(result.unit, content);
  result.unit.accept(visitor);
  return {
    'file': file.uri.toFilePath(),
    'diagnostics': diagnostics,
    'comments': _comments(result.unit),
    'functions': visitor.functions,
    'calls': visitor.calls,
  };
}

void main(List<String> arguments) {
  if (arguments.length < 3 || arguments.first != '--project-root') {
    _fail('usage: dart_syntax_facts.dart --project-root <root> <source> [...]');
  }
  final root = Directory(arguments[1]).absolute.path;
  final files = arguments.skip(2).map((path) => _analyze(root, path)).toList();
  stdout.writeln(
    jsonEncode({
      'schema_version': 1,
      'analyzer': 'package:analyzer',
      'analyzer_version': '14.1.0',
      'files': files,
    }),
  );
}
