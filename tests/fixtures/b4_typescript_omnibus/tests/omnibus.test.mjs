import assert from "node:assert/strict";
import test from "node:test";
import { loadInvoiceRecord, saveInventoryRecord } from "../.test-dist/omnibus.js";

test("the locked TypeScript host compiles and retains exported behavior", () => {
  assert.deepEqual(loadInvoiceRecord("invoice-1"), { id: "invoice-1" });
  assert.deepEqual(saveInventoryRecord({ id: "inventory-1" }), { id: "inventory-1" });
});
