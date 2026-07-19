export const first = 1, second = 2;

const openBracePattern = /\{/;

export function afterRegex(): RegExp {
  return openBracePattern;
}
