export type VerifiedWebhook = {
  deliveryId: string;
  body: string;
  signature: string;
};

export function acceptsWebhook(message: VerifiedWebhook): boolean {
  return message.signature.length > 0 && message.body.length > 0;
}

export function sourceName(message: VerifiedWebhook): string {
  return `webhook:${message.deliveryId}`;
}
