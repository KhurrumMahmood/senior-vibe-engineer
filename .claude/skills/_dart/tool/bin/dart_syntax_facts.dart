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

int _endLine(CompilationUnit unit, AstNode node) {
  final offset = node.end > node.offset ? node.end - 1 : node.offset;
  return unit.lineInfo.getLocation(offset).lineNumber;
}

Map<String, Object?> _directiveFact(Directive node, CompilationUnit unit) {
  late final String kind;
  String? uri;
  var supported = true;
  String? unsupportedReason;
  if (node is ImportDirective) {
    kind = 'import';
    uri = node.uri.stringValue;
    if (node.configurations.isNotEmpty) {
      supported = false;
      unsupportedReason = 'conditional_configuration';
    }
  } else if (node is ExportDirective) {
    kind = 'export';
    uri = node.uri.stringValue;
    if (node.configurations.isNotEmpty) {
      supported = false;
      unsupportedReason = 'conditional_configuration';
    }
  } else if (node is PartDirective) {
    kind = 'part';
    uri = node.uri.stringValue;
  } else if (node is PartOfDirective) {
    kind = 'part_of';
    uri = node.uri?.stringValue;
  } else {
    throw StateError('unhandled directive ${node.runtimeType}');
  }
  final location = unit.lineInfo.getLocation(node.offset);
  return {
    'kind': kind,
    'uri': uri,
    'offset': node.offset,
    'end': node.end,
    'line': location.lineNumber,
    'column': location.columnNumber,
    'supported': supported,
    'unsupported_reason': unsupportedReason,
  };
}

List<Map<String, Object?>> _directives(CompilationUnit unit) {
  final rows = <Map<String, Object?>>[];
  for (final directive in unit.directives) {
    if (directive is ImportDirective ||
        directive is ExportDirective ||
        directive is PartDirective ||
        directive is PartOfDirective) {
      rows.add(_directiveFact(directive, unit));
    }
  }
  return rows;
}

bool _privateName(String? name) => name?.startsWith('_') ?? false;

final class _Container {
  const _Container(this.name, this.offset, this.isPrivate);

  final String? name;
  final int offset;
  final bool isPrivate;
}

class _DirectBodyVisitor extends RecursiveAstVisitor<void> {
  _DirectBodyVisitor(this.unit, this.declarationOffset);

  final CompilationUnit unit;
  final int declarationOffset;
  final List<Map<String, Object?>> events = [];

  void _event(String kind, Token token) {
    final location = unit.lineInfo.getLocation(token.offset);
    events.add({
      'declaration_offset': declarationOffset,
      'kind': kind,
      'offset': token.offset,
      'end': token.end,
      'line': location.lineNumber,
      'column': location.columnNumber,
    });
  }

  @override
  void visitFunctionDeclarationStatement(FunctionDeclarationStatement node) {}

  @override
  void visitFunctionExpression(FunctionExpression node) {}

  @override
  void visitIfStatement(IfStatement node) {
    _event('if', node.ifKeyword);
    super.visitIfStatement(node);
  }

  @override
  void visitForStatement(ForStatement node) {
    _event('for', node.forKeyword);
    super.visitForStatement(node);
  }

  @override
  void visitWhileStatement(WhileStatement node) {
    _event('while', node.whileKeyword);
    super.visitWhileStatement(node);
  }

  @override
  void visitDoStatement(DoStatement node) {
    _event('do', node.doKeyword);
    super.visitDoStatement(node);
  }

  @override
  void visitSwitchCase(SwitchCase node) {
    _event('switch_case', node.keyword);
    super.visitSwitchCase(node);
  }

  @override
  void visitSwitchPatternCase(SwitchPatternCase node) {
    _event('switch_case', node.keyword);
    super.visitSwitchPatternCase(node);
  }

  @override
  void visitCatchClause(CatchClause node) {
    _event('catch', node.catchKeyword ?? node.onKeyword!);
    super.visitCatchClause(node);
  }

  @override
  void visitBinaryExpression(BinaryExpression node) {
    if (node.operator.type == TokenType.AMPERSAND_AMPERSAND) {
      _event('logical_and', node.operator);
    } else if (node.operator.type == TokenType.BAR_BAR) {
      _event('logical_or', node.operator);
    }
    super.visitBinaryExpression(node);
  }
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
  final List<_Container> _containers = [];
  final List<Map<String, Object?>> functions = [];
  final List<Map<String, Object?>> calls = [];
  final List<Map<String, Object?>> declarations = [];
  final List<Map<String, Object?>> namedBodies = [];
  final List<Map<String, Object?>> directBodyBranches = [];
  final List<Map<String, Object?>> bodyTokens = [];

  void _declaration(
    AstNode node, {
    required String? name,
    required String kind,
    required bool topLevel,
    required bool isPrivate,
    required bool anonymous,
    Token? augmentKeyword,
  }) {
    final container = _containers.isEmpty ? null : _containers.last;
    final location = unit.lineInfo.getLocation(node.offset);
    declarations.add({
      'name': name,
      'kind': kind,
      'container': container?.name,
      'container_offset': container?.offset,
      'top_level': topLevel,
      'private': isPrivate || (container?.isPrivate ?? false),
      'anonymous': anonymous,
      'offset': node.offset,
      'end': node.end,
      'line': location.lineNumber,
      'end_line': _endLine(unit, node),
      'supported': augmentKeyword == null,
      'unsupported_reason': augmentKeyword == null
          ? null
          : 'augmentation_declaration',
    });
  }

  void _body(
    AstNode declaration,
    FunctionBody body, {
    required String name,
    required String kind,
  }) {
    final container = _containers.isEmpty ? null : _containers.last;
    final bodyLocation = unit.lineInfo.getLocation(body.offset);
    namedBodies.add({
      'name': name,
      'kind': kind,
      'container': container?.name,
      'declaration_offset': declaration.offset,
      'declaration_end': declaration.end,
      'body_offset': body.offset,
      'body_end': body.end,
      'body_line': bodyLocation.lineNumber,
      'body_end_line': _endLine(unit, body),
    });

    Token? token = body.beginToken;
    var index = 0;
    while (token != null && !token.isEof && token.offset < body.end) {
      bodyTokens.add({
        'declaration_offset': declaration.offset,
        'index': index,
        'token_kind': token.type.name,
        'lexeme': token.lexeme,
        'offset': token.offset,
        'end': token.end,
      });
      index++;
      token = token.next;
    }

    final branches = _DirectBodyVisitor(unit, declaration.offset);
    body.accept(branches);
    branches.events.sort(
      (left, right) =>
          (left['offset'] as int).compareTo(right['offset'] as int),
    );
    directBodyBranches.addAll(branches.events);
  }

  void _pushContainer(
    AstNode node,
    String? name,
    bool isPrivate,
    void Function() visitChildren,
  ) {
    _containers.add(_Container(name, node.offset, isPrivate));
    visitChildren();
    _containers.removeLast();
  }

  void _containerDeclaration(
    AstNode node, {
    required String? name,
    required String kind,
    required Token? augmentKeyword,
    required void Function() visitChildren,
  }) {
    final isPrivate = name == null || _privateName(name);
    _declaration(
      node,
      name: name,
      kind: kind,
      topLevel: true,
      isPrivate: isPrivate,
      anonymous: name == null,
      augmentKeyword: augmentKeyword,
    );
    _pushContainer(node, name, isPrivate, visitChildren);
  }

  void _typeAlias(TypeAlias node, void Function() visitChildren) {
    final name = node.name.lexeme;
    _declaration(
      node,
      name: name,
      kind: 'typedef',
      topLevel: true,
      isPrivate: _privateName(name),
      anonymous: false,
      augmentKeyword: node.augmentKeyword,
    );
    visitChildren();
  }

  @override
  void visitClassDeclaration(ClassDeclaration node) {
    _containerDeclaration(
      node,
      name: node.namePart.typeName.lexeme,
      kind: 'class',
      augmentKeyword: node.augmentKeyword,
      visitChildren: () => super.visitClassDeclaration(node),
    );
  }

  @override
  void visitEnumDeclaration(EnumDeclaration node) {
    _containerDeclaration(
      node,
      name: node.namePart.typeName.lexeme,
      kind: 'enum',
      augmentKeyword: node.augmentKeyword,
      visitChildren: () => super.visitEnumDeclaration(node),
    );
  }

  @override
  void visitExtensionDeclaration(ExtensionDeclaration node) {
    _containerDeclaration(
      node,
      name: node.name?.lexeme,
      kind: 'extension',
      augmentKeyword: node.augmentKeyword,
      visitChildren: () => super.visitExtensionDeclaration(node),
    );
  }

  @override
  void visitMixinDeclaration(MixinDeclaration node) {
    _containerDeclaration(
      node,
      name: node.name.lexeme,
      kind: 'mixin',
      augmentKeyword: node.augmentKeyword,
      visitChildren: () => super.visitMixinDeclaration(node),
    );
  }

  @override
  void visitFunctionTypeAlias(FunctionTypeAlias node) {
    _typeAlias(node, () => super.visitFunctionTypeAlias(node));
  }

  @override
  void visitGenericTypeAlias(GenericTypeAlias node) {
    _typeAlias(node, () => super.visitGenericTypeAlias(node));
  }

  @override
  void visitFunctionDeclaration(FunctionDeclaration node) {
    if (node.parent is CompilationUnit) {
      final name = node.name.lexeme;
      final kind = node.isGetter
          ? 'getter'
          : node.isSetter
          ? 'setter'
          : 'top_level_function';
      _declaration(
        node,
        name: name,
        kind: kind,
        topLevel: true,
        isPrivate: _privateName(name),
        anonymous: false,
        augmentKeyword: node.augmentKeyword,
      );
      _body(node, node.functionExpression.body, name: name, kind: kind);
      if (!node.isGetter && !node.isSetter) {
        final fact = _functionFact(
          node,
          name,
          node.functionExpression.body,
          unit,
          content,
        );
        if (fact != null) functions.add(fact);
      }
    }
    super.visitFunctionDeclaration(node);
  }

  @override
  void visitMethodDeclaration(MethodDeclaration node) {
    if (_containers.isNotEmpty) {
      final name = node.name.lexeme;
      final kind = node.isGetter
          ? 'getter'
          : node.isSetter
          ? 'setter'
          : node.isOperator
          ? 'operator'
          : 'method';
      _declaration(
        node,
        name: name,
        kind: kind,
        topLevel: false,
        isPrivate: _privateName(name),
        anonymous: false,
        augmentKeyword: node.augmentKeyword,
      );
      _body(node, node.body, name: name, kind: kind);
    }
    super.visitMethodDeclaration(node);
  }

  @override
  void visitConstructorDeclaration(ConstructorDeclaration node) {
    if (_containers.isNotEmpty) {
      final container = _containers.last;
      final suffix = node.name?.lexeme;
      final name = suffix == null
          ? container.name ?? '<anonymous-constructor@${node.offset}>'
          : '${container.name ?? '<anonymous@${container.offset}>'}.$suffix';
      _declaration(
        node,
        name: name,
        kind: 'constructor',
        topLevel: false,
        isPrivate: _privateName(suffix),
        anonymous: false,
        augmentKeyword: node.augmentKeyword,
      );
      _body(node, node.body, name: name, kind: 'constructor');
    }
    super.visitConstructorDeclaration(node);
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
    'directives': _directives(result.unit),
    'declarations': visitor.declarations,
    'named_bodies': visitor.namedBodies,
    'direct_body_branches': visitor.directBodyBranches,
    'body_tokens': visitor.bodyTokens,
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
