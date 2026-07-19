import { _quoteNormalize, quotePrice } from "./legacy/order-workflow";

export const directTotal = quotePrice({ subtotal: _quoteNormalize(12), discount: 2 });
