export type DeliveryRequest = {
  deliveryId: string;
  body: string;
  signature: string;
};

export function acceptsWebhook(request: DeliveryRequest): boolean {
  return request.signature.length > 0 && request.body.length > 0;
}
