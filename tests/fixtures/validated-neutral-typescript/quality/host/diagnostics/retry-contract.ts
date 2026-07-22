import { retryDelay } from "../src/worker/retry.js";

const queueRetry: (attempt: number) => Promise<number> = retryDelay;

void queueRetry;
