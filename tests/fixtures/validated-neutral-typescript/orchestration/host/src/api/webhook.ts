import { deliveryMetricName } from "../metrics/delivery.js";

export type DeliveryRequest = {
  deliveryId: string;
  body: string;
  signature: string;
};

export function acceptedMetric(request: DeliveryRequest): string | null {
  if (request.signature.length === 0 || request.body.length === 0) {
    return null;
  }
  return deliveryMetricName("accepted");
}
