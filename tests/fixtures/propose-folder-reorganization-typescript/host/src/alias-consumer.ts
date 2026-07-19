import { parseInvoice } from "@app/billing-parser";

export const parsedAmount = parseInvoice("20").amount;
