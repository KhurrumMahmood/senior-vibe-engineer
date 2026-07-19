export type DeliveryJob = {
  deliveryId: string;
  attempt: number;
};

export function nextAttempt(job: DeliveryJob): number {
  return job.attempt + 1;
}
