import { settlementCapture } from "@orders/legacy/order-workflow";

export const aliasTotal = settlementCapture({ subtotal: 9, discount: 0 });
