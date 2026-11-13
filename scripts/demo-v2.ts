// SAMPLE DATA demo. Testnet execution is for Bob outside OpenClaw only.
import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { Account, JsonRpcProvider, KeyPairSigner } from "near-api-js";
import { startSandboxEnv, deployMarket } from "../agent/src/env.ts";
import { call, view, nearToYocto, explorerTx, type TxResult } from "../agent/src/near.ts";
import { parseQuery } from "../agent/src/v2/query.ts";
import { buildExcerpts, selectExcerpts, type Excerpt } from "../agent/src/v2/excerpt.ts";
import { loadKeywordFeed, replayFeed } from "../agent/src/v2/feed-v2.ts";
import { OralysOracleV2 } from "../agent/src/v2/oracle-v2.ts";

function option(name: string): string | undefined {
  const i = process.argv.indexOf(name);
  if (i < 0) return undefined;
  const value = process.argv[i + 1];
  if (!value || value.startsWith("--")) throw new Error(`missing value for ${name}`);
  return value;
}
const selectedNetwork = option("--network") ?? "sandbox";
const network: "sandbox" | "testnet" = selectedNetwork as "sandbox" | "testnet";
if (network !== "sandbox" && network !== "testnet") throw new Error("network must be sandbox or testnet");
const root = fileURLToPath(new URL("../", import.meta.url));
const base = `${root}demo-output/demo-v2-${network}`;
const lines: string[] = [];
const transactions: Array<{ step: string; hash: string; ok: boolean; error?: string; link?: string; at: string }> = [];
function flush() {
  mkdirSync(`${root}demo-output`, { recursive: true });
  writeFileSync(`${base}.log`, lines.join("\n") + "\n");
  writeFileSync(`${base}-txs.json`, JSON.stringify(transactions, null, 2) + "\n");
}
function out(line: string) { console.log(line); lines.push(line); flush(); }
function record(step: string, tx: TxResult) {
  transactions.push({ step, hash: tx.hash, ok: tx.ok, error: tx.error,
    link: explorerTx(network, tx.hash), at: new Date().toISOString() });
  out(`${step}: ${tx.ok ? "ok" : `REJECTED, ${tx.error}`} (tx ${tx.hash})`);
}
const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

async function main() {
  out(`Oralys v2 keyword requests on ${network}. SAMPLE DATA only.`);
  out("NEAR is Oralys's home chain. Tracks: Agent Economy, Open Innovation and Privacy.");
  let stop: () => Promise<void> = async () => {};
  try {
    let buyer: Account;
    let seller: Account;
    let provider: JsonRpcProvider;
    let contractId: string;
    let oracle: OralysOracleV2;
    if (network === "sandbox") {
      // Fail before starting a sandbox or downloading anything if the build is missing.
      const wasm = readFileSync(`${root}contract-v2/target/near/oralys_signal_market_v2.wasm`);
      oracle = new OralysOracleV2(OralysOracleV2.generateKeys());
      const env = await startSandboxEnv(out);
      stop = () => env.stop();
      buyer = env.buyer; seller = env.seller; provider = env.provider;
      contractId = env.market.accountId;
      await deployMarket(env, oracle.publicKey, wasm, out);
      for (const tx of env.setupTxs) record(tx.label, { hash: tx.hash, ok: true, logs: [], events: [] });
    } else {
      // Existing files only. Never call testnetEnv, loadOrCreate, or deployMarket here.
      // These files are read only when Bob explicitly runs testnet outside OpenClaw.
      const buyerPath = option("--buyer-key");
      const sellerPath = option("--seller-key");
      const oraclePath = option("--oracle-key");
      if (!buyerPath || !sellerPath || !oraclePath) {
        throw new Error("testnet requires existing --buyer-key, --seller-key and --oracle-key files; Bob runs this outside OpenClaw");
      }
      contractId = process.env.MARKET2_ID ?? "market2.oralys-signal.testnet";
      if (!contractId.endsWith(".testnet")) throw new Error("MARKET2_ID must be a testnet account");
      provider = new JsonRpcProvider({ url: process.env.NEAR_RPC_URL ?? "https://test.rpc.fastnear.com" });
      const existingAccount = (path: string) => {
        const key = JSON.parse(readFileSync(path, "utf8"));
        if (typeof key.account_id !== "string" || !key.account_id.endsWith(".testnet")) throw new Error("existing account must be on testnet");
        return new Account(key.account_id, provider, KeyPairSigner.fromSecretKey(key.private_key));
      };
      buyer = existingAccount(buyerPath);
      seller = existingAccount(sellerPath);
      oracle = new OralysOracleV2(JSON.parse(readFileSync(oraclePath, "utf8")));
      const config = await view<{ signer_public_key: string; seller: string }>(provider, contractId, "get_config", {});
      assert.equal(config.signer_public_key, oracle.publicKey, "existing deployment must use this oracle");
      assert.equal(config.seller, seller.accountId, "existing deployment must use this seller");
    }
    const query = "NVIDIA OR (Clarity AND Act)";
    const parsed = parseQuery(query);
    const now = Math.floor(Date.now() / 1000);
    const segments = replayFeed(loadKeywordFeed(`${root}sample-data/keyword-feed.json`), now - 300);
    async function open(ttl: number) {
      const tx = await call(buyer, contractId, "open_request", {
        query, window_seconds: null, price_per_excerpt: nearToYocto("0.01").toString(), min_quality: 70, ttl_seconds: ttl,
      }, { depositYocto: nearToYocto("0.05") });
      record(`Open request with ${ttl} second deadline`, tx);
      assert.ok(tx.ok, "open request failed");
      return String(tx.value);
    }
    const request = (id: string) => view<{ opened_at_ns: string; deadline_ns: string; status: string; paid_count: number }>(provider, contractId, "get_request", { request_id: id });
    async function fulfill(id: string, excerpt: Excerpt, signer = oracle) {
      return call(seller, contractId, "fulfill_excerpt", {
        request_id: id, excerpt_id: excerpt.excerpt_id, excerpt_hash: excerpt.excerpt_hash,
        recorded_at: String(excerpt.recorded_at), quality_score: excerpt.quality_score,
        signature: signer.signExcerpt(contractId, id, excerpt.excerpt_id, excerpt.excerpt_hash, excerpt.recorded_at, excerpt.quality_score),
      });
    }
    async function reject(label: string, result: Promise<TxResult>, expected: string) {
      const tx = await result;
      record(label, tx);
      assert.equal(tx.ok, false, `${label} unexpectedly succeeded`);
      assert.ok(tx.error?.includes(expected), `${label}: expected ${expected}`);
    }
    const id = await open(600);
    const opened = await request(id);
    const excerpts = selectExcerpts(parsed, segments, {
      openedAtUnix: Number(BigInt(opened.opened_at_ns) / 1_000_000_000n),
      windowSeconds: 3600, nowUnix: Math.floor(Date.now() / 1000), minQuality: 70,
    });
    assert.deepEqual(excerpts.map((e) => e.excerpt_id), ["sd-r1-02-s2", "sd-r2-01-s2", "sd-r3-02-s2", "sd-r3-02-s5", "sd-r4-01-s1"]);
    const all = segments.flatMap((segment) => buildExcerpts(parsed, segment));
    const find = (excerptId: string) => { const e = all.find((e) => e.excerpt_id === excerptId); assert.ok(e); return e; };
    await reject("Forged signature", fulfill(id, excerpts[0], new OralysOracleV2(OralysOracleV2.generateKeys())), "invalid signature");
    await reject("Out of window", fulfill(id, find("sd-r1-01-s1")), "recorded_at is outside the request window");
    await reject("Low quality", fulfill(id, find("sd-r2-02-s1")), "quality score below buyer minimum");
    for (const [i, excerpt] of excerpts.entries()) {
      const tx = await fulfill(id, excerpt);
      record(`Pay ${excerpt.excerpt_id}`, tx);
      assert.ok(tx.ok, "excerpt payment failed");
      if (i === 0) await reject("Double pay", fulfill(id, excerpt), "excerpt already paid for this request");
    }
    const exhausted = await request(id);
    assert.equal(exhausted.status, "Exhausted");
    assert.equal(Number(exhausted.paid_count), 5);
    out("5 excerpts paid. Status: Exhausted.");
    const shortId = await open(20);
    const paid = await fulfill(shortId, excerpts[0]);
    record("Pay one excerpt on short request", paid);
    assert.ok(paid.ok, "short request payment failed");
    const short = await request(shortId);
    const waitMs = Math.max(0, Number(BigInt(short.deadline_ns) / 1_000_000n) - Date.now()) + 5000;
    out(`Wait ${Math.ceil(waitMs / 1000)} seconds for the refund deadline.`);
    await sleep(waitMs);
    let refunded = false;
    for (let attempt = 0; attempt < 7; attempt++) {
      const tx = await call(buyer, contractId, "refund", { request_id: shortId });
      record("Refund after deadline", tx);
      if (tx.ok) { refunded = true; break; }
      assert.ok(tx.error?.includes("deadline has not passed yet"), "unexpected refund failure");
      await sleep(5000);
    }
    assert.ok(refunded, "refund deadline was not reached");
    assert.equal((await request(shortId)).status, "Refunded");
    out("1 refund completed: 0.04 NEAR remaining budget. Status: Refunded.");
  } finally { await stop(); flush(); }
}
main().catch((error: unknown) => {
  // Do not dump signer objects or credential file contents on failures.
  out(network === "sandbox" && error instanceof Error ? error.message : "Demo failed; check the existing deployment and local configuration without printing keys.");
  process.exitCode = 1;
});
