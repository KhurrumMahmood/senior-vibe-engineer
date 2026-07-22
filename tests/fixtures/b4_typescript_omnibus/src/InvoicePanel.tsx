export type InvoiceProps = { id: string };

export function loadInvoiceRecord(id: string): InvoiceProps { return { id }; }
export const saveInvoiceRecord = (record: InvoiceProps): InvoiceProps => record;
export class InvoiceService { readonly domain = "invoice"; }
