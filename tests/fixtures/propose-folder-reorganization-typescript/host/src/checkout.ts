import { validateInvoice } from "./billing-validator";

export const canCheckout = validateInvoice("15");
