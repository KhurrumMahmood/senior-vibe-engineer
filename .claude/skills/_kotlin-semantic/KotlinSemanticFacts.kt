@file:OptIn(
    org.jetbrains.kotlin.config.CompilerConfiguration.Internals::class,
    org.jetbrains.kotlin.K1Deprecation::class,
)
@file:Suppress("DEPRECATION", "DEPRECATION_ERROR", "K1_API_DEPRECATION")

package engineering.skills.kotlinsemantic

import com.intellij.openapi.util.Disposer
import com.intellij.psi.PsiElement
import org.jetbrains.kotlin.cli.common.config.addKotlinSourceRoot
import org.jetbrains.kotlin.cli.common.messages.MessageCollector
import org.jetbrains.kotlin.cli.jvm.compiler.EnvironmentConfigFiles
import org.jetbrains.kotlin.cli.jvm.compiler.KotlinCoreEnvironment
import org.jetbrains.kotlin.cli.jvm.compiler.NoScopeRecordCliBindingTrace
import org.jetbrains.kotlin.cli.jvm.compiler.TopDownAnalyzerFacadeForJVM
import org.jetbrains.kotlin.cli.jvm.config.addJvmClasspathRoot
import org.jetbrains.kotlin.cli.jvm.config.configureJdkClasspathRoots
import org.jetbrains.kotlin.config.CommonConfigurationKeys
import org.jetbrains.kotlin.config.CompilerConfiguration
import org.jetbrains.kotlin.config.JVMConfigurationKeys
import org.jetbrains.kotlin.descriptors.CallableDescriptor
import org.jetbrains.kotlin.descriptors.CallableMemberDescriptor
import org.jetbrains.kotlin.descriptors.ConstructorDescriptor
import org.jetbrains.kotlin.descriptors.DeclarationDescriptor
import org.jetbrains.kotlin.descriptors.DescriptorVisibility
import org.jetbrains.kotlin.renderer.DescriptorRenderer
import org.jetbrains.kotlin.lexer.KtTokens
import org.jetbrains.kotlin.psi.KtBinaryExpression
import org.jetbrains.kotlin.psi.KtCallExpression
import org.jetbrains.kotlin.psi.KtClass
import org.jetbrains.kotlin.psi.KtClassOrObject
import org.jetbrains.kotlin.psi.KtDotQualifiedExpression
import org.jetbrains.kotlin.psi.KtEnumEntry
import org.jetbrains.kotlin.psi.KtFile
import org.jetbrains.kotlin.psi.KtNamedDeclaration
import org.jetbrains.kotlin.psi.KtNamedFunction
import org.jetbrains.kotlin.psi.KtParameter
import org.jetbrains.kotlin.psi.KtProperty
import org.jetbrains.kotlin.psi.KtReferenceExpression
import org.jetbrains.kotlin.psi.KtStringTemplateExpression
import org.jetbrains.kotlin.psi.psiUtil.collectDescendantsOfType
import org.jetbrains.kotlin.psi.psiUtil.getParentOfType
import org.jetbrains.kotlin.resolve.BindingContext
import org.jetbrains.kotlin.resolve.DescriptorUtils

private fun json(value: Any?): String = when (value) {
    null -> "null"
    is Boolean, is Number -> value.toString()
    is String -> buildString {
        append('"')
        for (character in value) when (character) {
            '"' -> append("\\\"")
            '\\' -> append("\\\\")
            '\b' -> append("\\b")
            '\u000c' -> append("\\f")
            '\n' -> append("\\n")
            '\r' -> append("\\r")
            '\t' -> append("\\t")
            else -> if (character.code < 0x20) append("\\u%04x".format(character.code)) else append(character)
        }
        append('"')
    }
    is Map<*, *> -> value.entries.joinToString(prefix = "{", postfix = "}") {
        json(it.key.toString()) + ":" + json(it.value)
    }
    is Iterable<*> -> value.joinToString(prefix = "[", postfix = "]") { json(it) }
    else -> error("unsupported JSON value ${value::class}")
}

private fun KtFile.line(element: PsiElement): Int =
    (viewProvider.document?.getLineNumber(element.textOffset) ?: 0) + 1

private fun descriptorId(descriptor: DeclarationDescriptor?): String? = descriptor?.let {
    DescriptorUtils.getFqName(it).asString()
}

private fun signature(descriptor: DeclarationDescriptor?): String? = descriptor?.let {
    DescriptorRenderer.FQ_NAMES_IN_TYPES.render(it)
}

private fun visibility(descriptor: DeclarationDescriptor?): String =
    (descriptor as? org.jetbrains.kotlin.descriptors.DeclarationDescriptorWithVisibility)
        ?.visibility
        ?.let(DescriptorVisibility::name)
        ?: "local-or-unknown"

private fun caller(reference: PsiElement, context: BindingContext): Map<String, Any?>? {
    val function = reference.getParentOfType<KtNamedFunction>(strict = false) ?: return null
    val descriptor = context[BindingContext.DECLARATION_TO_DESCRIPTOR, function]
    return mapOf("fq_name" to descriptorId(descriptor), "signature" to signature(descriptor))
}

private fun callableParameters(descriptor: DeclarationDescriptor?): List<Map<String, Any?>> =
    (descriptor as? CallableDescriptor)?.valueParameters?.map {
        mapOf(
            "name" to it.name.asString(),
            "type" to DescriptorRenderer.FQ_NAMES_IN_TYPES.renderType(it.type),
            "declares_default" to it.declaresDefaultValue(),
            "vararg" to (it.varargElementType != null),
        )
    } ?: emptyList()

private fun declarationKind(declaration: KtNamedDeclaration): String? = when (declaration) {
    is KtEnumEntry -> "enum-entry"
    is KtClassOrObject -> when {
        declaration is org.jetbrains.kotlin.psi.KtObjectDeclaration -> "object"
        declaration is KtClass && declaration.isInterface() -> "interface"
        declaration is KtClass && declaration.isEnum() -> "enum"
        else -> "class"
    }
    is KtNamedFunction -> "function"
    is KtProperty -> "property"
    is KtParameter -> if (declaration.hasValOrVar()) "constructor-property" else null
    else -> null
}

private fun declarationRow(
    file: KtFile,
    declaration: KtNamedDeclaration,
    context: BindingContext,
): Map<String, Any?>? {
    val kind = declarationKind(declaration) ?: return null
    val descriptor = context[BindingContext.DECLARATION_TO_DESCRIPTOR, declaration]
    val callable = descriptor as? CallableDescriptor
    val overridden = (descriptor as? CallableMemberDescriptor)?.overriddenDescriptors.orEmpty()
    return linkedMapOf(
        "path" to file.virtualFilePath,
        "line" to file.line(declaration),
        "kind" to kind,
        "name" to declaration.name,
        "fq_name" to descriptorId(descriptor),
        "signature" to signature(descriptor),
        "visibility" to visibility(descriptor),
        "override" to declaration.hasModifier(KtTokens.OVERRIDE_KEYWORD),
        "overrides" to overridden.map { signature(it) }.sortedBy { it },
        "extension_receiver" to callable?.extensionReceiverParameter?.type?.let {
            DescriptorRenderer.FQ_NAMES_IN_TYPES.renderType(it)
        },
        "parameters" to callableParameters(descriptor),
        "return_type" to callable?.returnType?.let {
            DescriptorRenderer.FQ_NAMES_IN_TYPES.renderType(it)
        },
        "body" to (declaration as? KtNamedFunction)?.bodyExpression?.text,
        "initializer" to (declaration as? KtProperty)?.initializer?.text,
        "type_text" to when (declaration) {
            is KtProperty -> declaration.typeReference?.text
            is KtParameter -> declaration.typeReference?.text
            else -> null
        },
    )
}

private fun callRow(file: KtFile, call: KtCallExpression, context: BindingContext): Map<String, Any?> {
    val callee = call.calleeExpression as? KtReferenceExpression
    val descriptor = callee?.let { context[BindingContext.REFERENCE_TARGET, it] }
    val receiver = (call.parent as? KtDotQualifiedExpression)?.receiverExpression?.text
    return linkedMapOf(
        "path" to file.virtualFilePath,
        "line" to file.line(call),
        "source" to call.text,
        "callee" to callee?.text,
        "receiver" to receiver,
        "target_fq_name" to descriptorId(descriptor),
        "target_signature" to signature(descriptor),
        "target_kind" to if (descriptor is ConstructorDescriptor) "constructor" else "callable",
        "target_parameters" to callableParameters(descriptor),
        "caller" to caller(call, context),
        "arguments" to call.valueArguments.map {
            mapOf(
                "name" to it.getArgumentName()?.asName?.asString(),
                "source" to it.getArgumentExpression()?.text,
            )
        },
        "resolved" to (descriptor != null),
    )
}

private fun writeRow(file: KtFile, expression: KtBinaryExpression, context: BindingContext): Map<String, Any?>? {
    if (expression.operationToken !in setOf(
            KtTokens.EQ,
            KtTokens.PLUSEQ,
            KtTokens.MINUSEQ,
            KtTokens.MULTEQ,
            KtTokens.DIVEQ,
            KtTokens.PERCEQ,
        )
    ) return null
    val left = expression.left ?: return null
    val reference = when (left) {
        is KtReferenceExpression -> left
        is KtDotQualifiedExpression -> left.selectorExpression as? KtReferenceExpression
        else -> null
    }
    val descriptor = reference?.let { context[BindingContext.REFERENCE_TARGET, it] }
    return linkedMapOf(
        "path" to file.virtualFilePath,
        "line" to file.line(expression),
        "source" to expression.text,
        "target_fq_name" to descriptorId(descriptor),
        "target_signature" to signature(descriptor),
        "operator" to expression.operationReference.text,
        "value" to expression.right?.text,
        "string_literal" to (expression.right as? KtStringTemplateExpression)?.takeIf {
            !it.hasInterpolation()
        }?.entries?.joinToString(separator = "") { it.text },
        "caller" to caller(expression, context),
        "resolved" to (descriptor != null),
    )
}

fun main(args: Array<String>) {
    require(args.size >= 2) { "usage: <stdlib.jar> <source.kt>..." }
    val disposable = Disposer.newDisposable("kotlin-semantic-facts")
    try {
        val configuration = CompilerConfiguration().apply {
            put(CommonConfigurationKeys.MESSAGE_COLLECTOR_KEY, MessageCollector.NONE)
            put(CommonConfigurationKeys.MODULE_NAME, "engineering-skills-kotlin-semantic")
            put(JVMConfigurationKeys.JDK_HOME, java.io.File(System.getProperty("java.home")))
            addJvmClasspathRoot(java.io.File(args[0]))
            configureJdkClasspathRoots()
            for (source in args.drop(1)) addKotlinSourceRoot(source)
        }
        val environment = KotlinCoreEnvironment.createForProduction(
            disposable,
            configuration,
            EnvironmentConfigFiles.JVM_CONFIG_FILES,
        )
        @Suppress("UNCHECKED_CAST")
        val files = environment::class.java.getMethod("getSourceFiles").invoke(environment) as List<KtFile>
        val trace = NoScopeRecordCliBindingTrace(environment.project)
        TopDownAnalyzerFacadeForJVM.analyzeFilesWithJavaIntegration(
            environment.project,
            files,
            trace,
            configuration,
            environment::createPackagePartProvider,
        )
        val context = trace.bindingContext
        val declarations = mutableListOf<Map<String, Any?>>()
        val calls = mutableListOf<Map<String, Any?>>()
        val references = mutableListOf<Map<String, Any?>>()
        val writes = mutableListOf<Map<String, Any?>>()
        for (file in files.sortedBy { it.virtualFilePath }) {
            declarations += file.collectDescendantsOfType<KtNamedDeclaration>()
                .mapNotNull { declarationRow(file, it, context) }
            calls += file.collectDescendantsOfType<KtCallExpression>().map { callRow(file, it, context) }
            references += file.collectDescendantsOfType<KtReferenceExpression>().map { reference ->
                val descriptor = context[BindingContext.REFERENCE_TARGET, reference]
                linkedMapOf(
                    "path" to file.virtualFilePath,
                    "line" to file.line(reference),
                    "source" to reference.text,
                    "target_fq_name" to descriptorId(descriptor),
                    "target_signature" to signature(descriptor),
                    "caller" to caller(reference, context),
                    "resolved" to (descriptor != null),
                )
            }
            writes += file.collectDescendantsOfType<KtBinaryExpression>()
                .mapNotNull { writeRow(file, it, context) }
        }
        val diagnostics = context.diagnostics.all().map {
            mapOf(
                "severity" to it.severity.name,
                "factory" to it.factory.name,
                "path" to it.psiFile.virtualFile?.path,
                "line" to it.psiFile.viewProvider.document?.getLineNumber(it.textRanges.first().startOffset)?.plus(1),
            )
        }
        print(json(linkedMapOf(
            "schema_version" to 1,
            "declarations" to declarations,
            "calls" to calls,
            "references" to references,
            "writes" to writes,
            "diagnostics" to diagnostics,
        )))
        println()
    } finally {
        Disposer.dispose(disposable)
    }
}
