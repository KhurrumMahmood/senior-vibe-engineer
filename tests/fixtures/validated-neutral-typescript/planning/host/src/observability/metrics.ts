export type DeliveryMetric = {
  deliveryId: string;
  outcome: "accepted" | "rejected" | "retried";
};

export function metricName(metric: DeliveryMetric): string {
  return `delivery.${metric.outcome}`;
}
