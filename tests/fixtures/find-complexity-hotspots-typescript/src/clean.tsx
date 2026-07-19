export function cleanPanel(value: number): string {
  if (value > 0) return "positive";
  return "not-positive";
}

export const expressionBodyOnly = (value: number): string => value > 0 ? "positive" : "not-positive";
