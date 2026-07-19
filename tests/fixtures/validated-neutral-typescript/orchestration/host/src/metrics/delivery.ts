export type DeliveryOutcome = "accepted" | "rejected" | "retried";

export function deliveryMetricName(outcome: DeliveryOutcome): string {
  return `delivery.${outcome}`;
}
