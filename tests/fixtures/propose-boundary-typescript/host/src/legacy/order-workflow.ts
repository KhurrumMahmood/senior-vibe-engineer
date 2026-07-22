export type QuoteInput = { subtotal: number; discount: number };

export function quotePrice(input: QuoteInput): number {
  return _quoteNormalize(input.subtotal) - input.discount;
}

export function quotePreview(input: QuoteInput): string {
  return `quote:${quotePrice(input)}`;
}

export function _quoteNormalize(value: number): number {
  return Math.max(0, value);
}

export function settlementCapture(input: QuoteInput): number {
  return _quoteNormalize(input.subtotal);
}

export function settlementReceipt(input: QuoteInput): string {
  return `settlement:${settlementCapture(input)}`;
}

export function _settlementValidate(input: QuoteInput): boolean {
  return input.discount >= 0;
}
