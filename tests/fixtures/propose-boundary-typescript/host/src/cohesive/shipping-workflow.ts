export function shippingQuote(weight: number): number {
  return _shippingNormalize(weight) * 3;
}

export function shippingSchedule(weight: number): string {
  return `scheduled:${shippingQuote(weight)}`;
}

export function shippingConfirm(weight: number): boolean {
  return shippingQuote(weight) > 0;
}

function _shippingNormalize(weight: number): number {
  return Math.max(0, weight);
}
