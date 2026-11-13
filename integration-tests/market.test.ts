// Sandbox integration tests. Runs the real wasm on a local near-sandbox node.
// Uses SAMPLE DATA from sample-data/signal-feed.json and throwaway keys only.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { startSandboxEnv, deployMarket, DEFAULT_WASM, type MarketEnv } from "../agent/src/env.ts";
import { OralysOracle } from "../agent/src/oracle.ts";
import { BuyerAgent } from "../agent/src/buyer-agent.ts";
import { SellerOracle } from "../agent/src/seller.ts";
import { loadFeed } from "../agent/src/feed.ts";
import { balance, nearToYocto, view } from "../agent/src/near.ts";

const feed = loadFeed(new URL("../sample-data/signal-feed.json", import.meta.url).pathname);
const sig = (id: string) => feed.signals.find((s) => s.signal_id === id)!;

let env: MarketEnv;
let oracle: OralysOracle;
let buyer: BuyerAgent;
let seller: SellerOracle;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

before(async () => {
  env = await startSandboxEnv();
  oracle = new OralysOracle(OralysOracle.generateKeys()); // in-memory, test only
  await deployMarket(env, oracle.publicKey, readFileSync(DEFAULT_WASM));
  buyer = new BuyerAgent({
    account: env.buyer,
    provider: env.provider,
    contractId: env.market.accountId,
    budgetNear: "1",
    minQuality: 70,
    ttlSeconds: 300,
  });
  seller = new SellerOracle(env.seller, oracle, env.market.accountId);
});

after(async () => {
  await env?.stop();
});

test("config reflects the registered signer and seller", async () => {
  const cfg: any = await view(env.provider, env.market.accountId, "get_config");
  assert.equal(cfg.signer_public_key, oracle.publicKey);
  assert.equal(cfg.seller, env.seller.accountId);
});

test("signing message matches the contract byte for byte", async () => {
  const s = sig("sample-001");
  const h = oracle.keyedHash(s.transcript);
  const onchain = await view<string>(env.provider, env.market.accountId, "get_signing_message", {
    request_id: "7", signal_id: s.signal_id, keyed_hash: h, quality_score: 88,
  });
  assert.equal(onchain, OralysOracle.signingMessage(env.market.accountId, 7, s.signal_id, h, 88));
});

test("valid signed fulfillment pays the seller", async () => {
  const s = sig("sample-001");
  const before = await balance(env.provider, env.seller.accountId);
  const opened = await buyer.openRequest(s);
  assert.ok(opened.tx.events.some((e) => e.event === "request_opened"));
  const tx = await seller.fulfill(opened.requestId, s);
  assert.equal(tx.ok, true, tx.error ?? "");
  assert.ok(tx.events.some((e) => e.event === "request_fulfilled"));
  const req = await buyer.getRequest(opened.requestId);
  assert.equal(req.status, "Fulfilled");
  const f = await buyer.getFulfillment(opened.requestId);
  assert.equal(f.quality_score, 88);
  assert.equal(f.keyed_hash, oracle.keyedHash(s.transcript));
  const after = await balance(env.provider, env.seller.accountId);
  // Seller pays gas for the fulfill call, so it gains the price minus a little gas.
  const gain = after - before;
  const price = nearToYocto(s.price_near);
  assert.ok(gain > price - nearToYocto("0.01") && gain <= price, `seller gain ${gain} vs price ${price}`);
});

test("signature from a different key is rejected and escrow stays open", async () => {
  const s = sig("sample-004");
  const opened = await buyer.openRequest(s);
  const imposter = new OralysOracle(OralysOracle.generateKeys());
  const tx = await seller.fulfill(opened.requestId, s, { signWith: imposter });
  assert.equal(tx.ok, false);
  assert.match(tx.error ?? "", /invalid signature/);
  assert.equal((await buyer.getRequest(opened.requestId)).status, "Open");
});

test("tampered score (signed 74, submitted 95) is rejected", async () => {
  const s = sig("sample-002");
  const opened = await buyer.openRequest(s);
  const keyedHash = oracle.keyedHash(s.transcript);
  const signature = oracle.signFulfillment(env.market.accountId, opened.requestId, s.signal_id, keyedHash, 74);
  const { call } = await import("../agent/src/near.ts");
  const tx = await call(env.seller, env.market.accountId, "fulfill", {
    request_id: opened.requestId, signal_id: s.signal_id, keyed_hash: keyedHash, quality_score: 95, signature,
  });
  assert.equal(tx.ok, false);
  assert.match(tx.error ?? "", /invalid signature/);
});

test("validly signed score below the buyer minimum is rejected", async () => {
  const s = sig("sample-003"); // score 52
  const opened = await buyer.openRequest(s, { minQuality: 70 });
  const tx = await seller.fulfill(opened.requestId, s);
  assert.equal(tx.ok, false);
  assert.match(tx.error ?? "", /quality score below buyer minimum/);
  assert.equal((await buyer.getRequest(opened.requestId)).status, "Open");
});

test("double fulfillment is rejected without changing fulfillment or paying again", async () => {
  const s = sig("sample-001");
  const opened = await buyer.openRequest(s);
  const before = await balance(env.provider, env.seller.accountId);
  const first = await seller.fulfill(opened.requestId, s);
  assert.equal(first.ok, true, first.error ?? "");
  assert.equal((await buyer.getRequest(opened.requestId)).status, "Fulfilled");
  const fulfillment = await buyer.getFulfillment(opened.requestId);
  assert.equal(fulfillment.request_id, opened.requestId);
  assert.equal(fulfillment.signal_id, s.signal_id);
  assert.equal(fulfillment.keyed_hash, oracle.keyedHash(s.transcript));
  assert.equal(fulfillment.quality_score, s.quality_score);
  assert.equal(fulfillment.seller, env.seller.accountId);
  const price = nearToYocto(s.price_near);
  assert.equal(fulfillment.paid, price.toString());
  const afterFirst = await balance(env.provider, env.seller.accountId);
  const gain = afterFirst - before;
  assert.ok(gain > price - nearToYocto("0.01") && gain <= price, `seller gain ${gain} vs price ${price}`);

  // The helper signs again with the registered oracle for the same request.
  const second = await seller.fulfill(opened.requestId, s);
  assert.equal(second.ok, false);
  assert.match(second.error ?? "", /request is not open/);
  assert.equal((await buyer.getRequest(opened.requestId)).status, "Fulfilled");
  assert.deepEqual(await buyer.getFulfillment(opened.requestId), fulfillment);
  const afterSecond = await balance(env.provider, env.seller.accountId);
  // A rejected call can cost gas, but must not pay the seller again.
  assert.ok(
    afterSecond <= afterFirst && afterSecond > afterFirst - nearToYocto("0.01"),
    `seller balance after retry ${afterSecond} vs before retry ${afterFirst}`,
  );
});

test("refund after the deadline returns the budget to the buyer", async () => {
  const s = sig("sample-006");
  const opened = await buyer.openRequest(s, { ttlSeconds: 2 });
  const early = await buyer.refund(opened.requestId);
  assert.equal(early.ok, false);
  assert.match(early.error ?? "", /deadline has not passed yet/);
  await sleep(4000);
  const late = await seller.fulfill(opened.requestId, s);
  assert.equal(late.ok, false);
  assert.match(late.error ?? "", /request deadline has passed/);
  const before = await balance(env.provider, env.buyer.accountId);
  const tx = await buyer.refund(opened.requestId);
  assert.equal(tx.ok, true, tx.error ?? "");
  assert.ok(tx.events.some((e) => e.event === "request_refunded"));
  const after = await balance(env.provider, env.buyer.accountId);
  const price = nearToYocto(s.price_near);
  assert.ok(after - before > price - nearToYocto("0.01"), `buyer gain ${after - before}`);
  assert.equal((await buyer.getRequest(opened.requestId)).status, "Refunded");
});

test("buyer agent skips signals below its bar without spending", () => {
  const low = buyer.evaluate(sig("sample-005"));
  assert.equal(low.buy, false);
  assert.match(low.reason, /below my minimum/);
  assert.equal(buyer.evaluate(sig("sample-001")).buy, true);
});
