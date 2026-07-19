import { parseInvoice } from "./billing-parser";

export function validateInvoice(input: string): boolean {
  return parseInvoice(input).amount > 0;
}
