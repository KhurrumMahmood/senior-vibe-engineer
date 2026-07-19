import assert from "node:assert/strict";
import test from "node:test";

test("locked TypeScript fixture has a native test boundary", () => {
  assert.equal(4, 4);
});
