import assert from "node:assert/strict";
import test from "node:test";

test("locked TypeScript incomplete-sweep fixture has a native test boundary", () => {
  assert.equal("fixture", "fixture");
});
