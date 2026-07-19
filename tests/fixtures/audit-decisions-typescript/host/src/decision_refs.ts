// decision:0001
export const direct = "decision:9001";

/* decision:0002 */
export const block = "/* decision:9002 */";

/**
 * decision:0003
 */
export const documented = `decision:9003`;

const expression = `${/* decision:0001 */ "safe"}`;
const pattern = /decision:9004/;
const escapedCommentPattern = /\/\* decision:9005 \*\//;
const generic = <T,>(value: T) => {
  // decision:0003
  return value;
};

// decision:9999
export { expression, generic, pattern, escapedCommentPattern };
