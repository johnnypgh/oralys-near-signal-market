// SAMPLE DATA only. NEAR is Oralys's home chain. Local sandbox, no live network.
import assert from "node:assert/strict";
import { createHash, generateKeyPairSync, sign } from "node:crypto";
import { readFileSync } from "node:fs";
import { setTimeout as delay } from "node:timers/promises";
import test from "node:test";
import { deployMarket, startSandboxEnv } from "../agent/src/env.ts";
import { balance, call, nearToYocto, view, type TxResult } from "../agent/src/near.ts";

// Fail before starting a sandbox when the local build artifact is missing.
const wasm = readFileSync(new URL("../contract-v2/target/near/oralys_signal_market_v2.wasm", import.meta.url));
const price = nearToYocto("0.01");
interface Request {
  id: string;
  spent: string;
  paid_count: number;
  status: "Open" | "Exhausted" | "Refunded";
  opened_at_ns: string;
  deadline_ns: string;
}
interface Payout {
  excerpt_id: string;
  excerpt_hash: string;
  paid: string;
}
function base58(bytes: Uint8Array): string {
  const alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
  let n = BigInt(`0x${Buffer.from(bytes).toString("hex")}`);
  let result = "";
  while (n > 0n) {
    result = alphabet[Number(n % 58n)] + result;
    n /= 58n;
  }
  for (const b of bytes) {
    if (b !== 0) break;
    result = "1" + result;
  }
  return result;
}
function success(tx: TxResult): void { assert.equal(tx.ok, true, tx.error ?? "transaction failed"); }
function rejected(tx: TxResult, message: string): void {
  assert.equal(tx.ok, false, `expected rejection: ${message}`);
  assert.ok(tx.error?.includes(message), tx.error ?? "missing transaction error");
}

test("SAMPLE DATA keyword market v2 in local sandbox", { timeout: 180_000 }, async (t) => {
  const keys = generateKeyPairSync("ed25519");
  const der = keys.publicKey.export({ type: "spki", format: "der" });
  const publicKey = `ed25519:${base58(der.subarray(-32))}`;
  const env = await startSandboxEnv();
  try {
    await deployMarket(env, publicKey, wasm);
    const contractId = env.market.accountId;
    const read = <T>(method: string, args: Record<string, unknown> = {}) =>
      view<T>(env.provider, contractId, method, args);
    const getRequest = (id: string) => read<Request>("get_request", { request_id: id });
    const getPayouts = (id: string) => read<Payout[]>("get_payouts", { request_id: id });
    const open = async (budget = "0.05", ttl = 600): Promise<string> => {
      const tx = await call(env.buyer, contractId, "open_request", {
        query: "NVIDIA OR (Clarity AND Act)", window_seconds: null,
        price_per_excerpt: price.toString(), min_quality: 70, ttl_seconds: ttl,
      }, { depositYocto: nearToYocto(budget) });
      success(tx);
      assert.equal(typeof tx.value, "string");
      return tx.value as string;
    };
    const excerpt = (id: string, recordedAt = Math.floor(Date.now() / 1000) - 5, score = 80) => ({
      excerpt_id: id,
      excerpt_hash: createHash("sha256").update(`SAMPLE DATA. NVIDIA excerpt ${id}.`).digest("hex"),
      recorded_at: String(recordedAt), quality_score: score,
    });
    type Excerpt = ReturnType<typeof excerpt>;
    const message = (rid: string, e: Excerpt) =>
      `oralys-signal-v2|${contractId}|${rid}|${e.excerpt_id}|${e.excerpt_hash}|${e.recorded_at}|${e.quality_score}`;
    const fulfill = (rid: string, e: Excerpt, signature?: string) =>
      // Submitted by a separate relayer (the sandbox root), so the seller pays no gas and
      // its balance change is exactly the payouts the contract sent.
      call(env.root, contractId, "fulfill_excerpt", {
        request_id: rid, ...e,
        signature: signature ?? sign(null, Buffer.from(message(rid, e)), keys.privateKey).toString("hex"),
      });

    await t.test("config and exact signing message", async () => {
      const config = await read<{ signing_domain: string; default_window_seconds: number }>("get_config");
      assert.equal(config.signing_domain, "oralys-signal-v2");
      assert.equal(config.default_window_seconds, 3600);
      const e = excerpt("sd-message");
      assert.equal(await read<string>("get_signing_message", { request_id: "42", ...e }), message("42", e));
    });

    await t.test("four excerpts pay 0.04 NEAR and preserve hashes and pay order", async () => {
      const rid = await open();
      const before = await balance(env.provider, env.seller.accountId);
      const excerpts = Array.from({ length: 4 }, (_, i) => excerpt(`sd-happy-${i}`));
      for (const e of excerpts) success(await fulfill(rid, e));
      assert.equal((await balance(env.provider, env.seller.accountId)) - before, 4n * price);
      const r = await getRequest(rid);
      assert.equal(r.paid_count, 4); assert.equal(r.spent, (4n * price).toString());
      assert.equal(r.status, "Open");
      const payouts = await getPayouts(rid);
      assert.deepEqual(payouts.map(p => p.excerpt_id), excerpts.map(e => e.excerpt_id));
      assert.deepEqual(payouts.map(p => p.excerpt_hash), excerpts.map(e => e.excerpt_hash));
      assert.ok(payouts.every(p => p.paid === price.toString()));
    });

    await t.test("bad signature leaves spent at zero", async () => {
      const rid = await open();
      rejected(await fulfill(rid, excerpt("sd-forged"), "00".repeat(64)), "invalid signature");
      assert.equal((await getRequest(rid)).spent, "0");
      assert.deepEqual(await getPayouts(rid), []);
    });

    await t.test("recording outside request window is rejected", async () => {
      const rid = await open();
      const opened = Number(BigInt((await getRequest(rid)).opened_at_ns) / 1_000_000_000n);
      rejected(await fulfill(rid, excerpt("sd-old", opened - 3601)), "recorded_at is outside the request window");
      assert.equal((await getRequest(rid)).spent, "0");
    });

    await t.test("low quality is rejected", async () => {
      const rid = await open();
      rejected(await fulfill(rid, excerpt("sd-low", undefined, 69)), "quality score below buyer minimum");
      assert.equal((await getRequest(rid)).spent, "0");
    });

    await t.test("duplicate excerpt does not pay seller twice", async () => {
      const rid = await open(); const e = excerpt("sd-duplicate");
      success(await fulfill(rid, e));
      const before = await balance(env.provider, env.seller.accountId);
      rejected(await fulfill(rid, e), "excerpt already paid for this request");
      const after = await balance(env.provider, env.seller.accountId);
      assert.equal(after, before, "seller must not gain another payout");
      assert.equal((await getRequest(rid)).paid_count, 1);
      assert.equal((await getRequest(rid)).spent, price.toString());
      assert.equal((await getPayouts(rid)).length, 1);
    });

    await t.test("0.02 budget pays twice then becomes Exhausted", async () => {
      const rid = await open("0.02");
      success(await fulfill(rid, excerpt("sd-budget-1")));
      success(await fulfill(rid, excerpt("sd-budget-2")));
      rejected(await fulfill(rid, excerpt("sd-budget-3")), "request is not open");
      const r = await getRequest(rid);
      assert.equal(r.status, "Exhausted"); assert.equal(r.paid_count, 2);
      assert.equal(r.spent, (2n * price).toString());
    });

    await t.test("five second request pays once and refunds only after deadline", async () => {
      const rid = await open("0.03", 5);
      success(await fulfill(rid, excerpt("sd-refund")));
      rejected(await call(env.buyer, contractId, "refund", { request_id: rid }), "deadline has not passed yet");
      const r = await getRequest(rid);
      const deadlineMs = Number(BigInt(r.deadline_ns) / 1_000_000n);
      await delay(Math.max(0, deadlineMs + 2000 - Date.now()));
      const before = await balance(env.provider, env.buyer.accountId);
      // Anyone may trigger the refund. The relayer sends it, so the buyer's gain is exact.
      const tx = await call(env.root, contractId, "refund", { request_id: rid });
      success(tx);
      assert.equal((await balance(env.provider, env.buyer.accountId)) - before, 2n * price);
      assert.equal((await getRequest(rid)).status, "Refunded");
      assert.equal((await getRequest(rid)).spent, price.toString());
      const refund = tx.events.find(e => e.event === "request_refunded");
      assert.deepEqual(refund?.data, [{ request_id: rid, buyer: env.buyer.accountId, amount: (2n * price).toString() }]);
    });
  } finally {
    await env.stop();
  }
});
