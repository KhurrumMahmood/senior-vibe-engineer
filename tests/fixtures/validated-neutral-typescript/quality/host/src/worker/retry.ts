export type RetryJob = {
  deliveryId: string;
  attempt: number;
};

export function retryDelay(attempt: number): number {
  return Math.min(30_000, 1000 * 2 ** attempt);
}

export function nextAttempt(job: RetryJob): RetryJob {
  return { ...job, attempt: job.attempt + 1 };
}
