// decision:0001 keeps the C syntax boundary explicit.
int anchored_decision(void)
{
    return 1;
}

/* decision:9999 is deliberately orphaned. */
int orphaned_decision(void)
{
    return 2;
}

const char *comment_shaped_line = "// decision:7777";
const char *comment_shaped_block = "/* decision:8888 */";
