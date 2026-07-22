export type RetryMetric = {
  deliveryId: string;
  outcome: "accepted" | "retried" | "failed";
};

export function metricName(metric: RetryMetric): string {
  return `delivery.${metric.outcome}`;
}

export function retryTag(attempt: number): string {
  return `attempt:${attempt}`;
}
