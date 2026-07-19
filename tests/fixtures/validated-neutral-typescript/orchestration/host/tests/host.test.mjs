import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("the locked host keeps one centralized delivery metric definition", async () => {
  const metric = await readFile(new URL("../src/metrics/delivery.ts", import.meta.url), "utf8");
  const webhook = await readFile(new URL("../src/api/webhook.ts", import.meta.url), "utf8");
  assert.match(metric, /deliveryMetricName/);
  assert.match(webhook, /deliveryMetricName\("accepted"\)/);
});
