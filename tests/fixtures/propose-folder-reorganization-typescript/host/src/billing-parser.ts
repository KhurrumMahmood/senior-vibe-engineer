import type { Invoice } from "./billing-types";

export function parseInvoice(input: string): Invoice {
  return { amount: Number(input) };
}
