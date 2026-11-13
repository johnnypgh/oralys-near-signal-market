// End to end demo: buyer agent pays for SAMPLE DATA signals that clear its quality bar,
// then shows the contract rejecting a forged signature and a low score, and refunding.
//
//   npx tsx scripts/demo.ts                       # local sandbox (default)
//   NEAR_ACCOUNT_ID=<you>.testnet npx tsx scripts/demo.ts --network testnet
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { baseEncode } from "near-api-js";
import { startSandboxEnv, testnetEnv, deployMarket, DEFAULT_WASM, type MarketEnv } from "../agent/src/env.ts";
import { OralysOracle } from "../agent/src/oracle.ts";
import { BuyerAgent } from "../agent/src/buyer-agent.ts";
import { SellerOracle } from "../agent/src/seller.ts";
import { loadFeed } from "../agent/src/feed.ts";
import { balance, explorerAccount, explorerTx, yoctoToNear, type Network, type TxResult } from "../agent/src/near.ts";

const network: Network = process.argv.includes("--network") && process.argv[process.argv.indexOf("--network") + 1] === "testnet" ? "testnet" : "sandbox";
const root = new URL("..", import.meta.url).pathname;
const feed = loadFeed(`${root}sample-data/signal-feed.json`);
const policy = JSON.parse(readFileSync(`${root}_shared/policy.json`, "utf8"));
const lines: string[] = [];
const txRecord: Array<{ step: string; hash: string; ok: boolean; error?: string; link?: string; at: string }> = [];
const startedAt = new Date().toISOString();
// Testnet runs write to notes/ after every tx, so an interrupted run still leaves its hashes.
const recordBase = network === "testnet" ? `${root}notes/testnet-run` : `${root}demo-output/demo-${network}-progress`;
const meta: Record<string, string> = {};

function flushRecord() {
  mkdirSync(`${root}${network === "testnet" ? "notes" : "demo-output"}`, { recursive: true });
  writeFileSync(`${recordBase}.json`, JSON.stringify({ network, started_at: startedAt, ...meta, txs: txRecord }, null, 2) + "\n");
  const md = [
    `# Oralys Signal Market ${network} demo run`,
    "",
    "SAMPLE DATA only. Testnet NEAR only, no real money.",
    "",
    `- Started: ${startedAt} (UTC)`,
    ...Object.entries(meta).map(([k, v]) => `- ${k}: ${v}`),
    "",
    "| # | Step | Result | Transaction |",
    "| --- | --- | --- | --- |",
    ...txRecord.map((t, i) => `| ${i + 1} | ${t.step} | ${t.ok ? "ok" : `rejected: ${t.error}`} | ${t.link ? `[${t.hash}](${t.link})` : t.hash} |`),
    "",
  ];
  writeFileSync(`${recordBase}.md`, md.join("\n"));
}

function out(msg = "") {
  console.log(msg);
  lines.push(msg);
}
function section(title: string) {
  out("");
  out(`== ${title} ==`);
}
function tx(step: string, t: TxResult | { hash: string; ok?: boolean }) {
  const ok = (t as TxResult).ok ?? true;
  const link = explorerTx(network, t.hash);
  txRecord.push({ step, hash: t.hash, ok, error: (t as TxResult).error, link, at: new Date().toISOString() });
  flushRecord();
  out(`   tx ${t.hash}${link ? `  ${link}` : ""}`);
}
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function main() {
  out("Oralys Signal Market demo (NEAR, Agent Economy and Open Innovation tracks)");
  out(`network: ${network}`);
  out(`feed: ${feed.feed}. ${feed.notice}`);

  section("1. Setup");
  let env: MarketEnv;
  if (network === "sandbox") {
    env = await startSandboxEnv(out);
  } else {
    const id = process.env.NEAR_ACCOUNT_ID;
    if (!id) throw new Error("set NEAR_ACCOUNT_ID to your testnet account");
    env = await testnetEnv(id, process.env.NEAR_RPC_URL ?? "https://test.rpc.fastnear.com", out);
  }
  try {
    const oracle = OralysOracle.loadOrCreate(`${root}.keys/oracle-${network}.json`);
    out(`market contract: ${env.market.accountId}`);
    out(`buyer agent:     ${env.buyer.accountId}`);
    out(`seller payout:   ${env.seller.accountId}`);
    out(`oracle signer public key: ${oracle.publicKey}`);
    meta.market = env.market.accountId;
    meta.buyer = env.buyer.accountId;
    meta.seller = env.seller.accountId;
    meta.signer_public_key = oracle.publicKey;
    for (const s of env.setupTxs) tx(s.label, { hash: s.hash });
    const wasm = readFileSync(DEFAULT_WASM);
    const localHash = baseEncode(createHash("sha256").update(wasm).digest());
    meta.wasm_sha256_bs58 = localHash;
    let upToDate = false;
    try {
      const st: any = await env.market.getState();
      const cfg: any = await (await import("../agent/src/near.ts")).view(env.provider, env.market.accountId, "get_config");
      upToDate = (st.codeHash ?? st.code_hash) === localHash && cfg.signer_public_key === oracle.publicKey && cfg.seller === env.seller.accountId;
    } catch {
      upToDate = false;
    }
    const before = env.setupTxs.length;
    if (upToDate) {
      out(`contract on ${env.market.accountId} already matches this build (${localHash}), not redeploying`);
    } else {
      await deployMarket(env, oracle.publicKey, wasm, out);
    }
    for (const s of env.setupTxs.slice(before)) {
      out(` - ${s.label}`);
      tx(s.label, { hash: s.hash });
    }

    const agent = new BuyerAgent({
      account: env.buyer,
      provider: env.provider,
      contractId: env.market.accountId,
      budgetNear: process.env.AGENT_BUDGET_NEAR ?? policy.budget_near,
      minQuality: Number(process.env.AGENT_MIN_QUALITY ?? policy.min_quality),
      ttlSeconds: policy.ttl_seconds,
    });
    const seller = new SellerOracle(env.seller, oracle, env.market.accountId);

    section("2. Buyer agent reads the feed and buys what clears its bar");
    out(`agent budget ${agent.opts.budgetNear} NEAR, minimum quality ${agent.opts.minQuality}`);
    const sellerStart = await balance(env.provider, env.seller.accountId);
    for (const s of feed.signals) {
      const d = agent.evaluate(s);
      out("");
      out(`[${s.signal_id}] ${s.title} (score ${s.quality_score}, ${s.price_near} NEAR)`);
      if (!d.buy) {
        out(` - SKIP: ${d.reason}`);
        continue;
      }
      out(` - BUY: ${d.reason}`);
      const opened = await agent.openRequest(s);
      out(` - opened request #${opened.requestId}, ${s.price_near} NEAR held in escrow`);
      tx(`open_request #${opened.requestId}`, opened.tx);
      const f = await seller.fulfill(opened.requestId, s);
      out(f.ok ? ` - oracle delivered a signed fulfillment, contract verified it and paid the seller` : ` - fulfillment failed: ${f.error}`);
      tx(`fulfill #${opened.requestId}`, f);
      const ff = await agent.getFulfillment(opened.requestId);
      if (ff) out(` - on chain record: signal ${ff.signal_id}, score ${ff.quality_score}, keyed hash ${ff.keyed_hash.slice(0, 16)}...`);
      out(` - agent budget left: ${yoctoToNear(agent.remainingYocto)} NEAR`);
    }
    const sellerEnd = await balance(env.provider, env.seller.accountId);
    out("");
    out(`seller balance change: +${yoctoToNear(sellerEnd - sellerStart)} NEAR (payments minus the seller's own gas)`);

    section("3. Guardrails enforced by the contract");
    const target = feed.signals.find((s) => s.signal_id === "sample-002")!;
    out(`buyer opens a stricter request for ${target.signal_id} (min quality 80, 20 second deadline)`);
    const strict = await agent.openRequest(target, { minQuality: 80, ttlSeconds: 20 });
    tx(`open_request #${strict.requestId}`, strict.tx);

    out("a) fulfillment signed by a key that is not the registered Oralys signer");
    const forged = await seller.fulfill(strict.requestId, target, { signWith: new OralysOracle(OralysOracle.generateKeys()) });
    out(`   result: ${forged.ok ? "ACCEPTED (unexpected)" : `REJECTED, ${forged.error}`}`);
    tx("fulfill with forged signature", forged);

    out(`b) genuine signature, but score ${target.quality_score} is below the buyer's 80`);
    const low = await seller.fulfill(strict.requestId, target);
    out(`   result: ${low.ok ? "ACCEPTED (unexpected)" : `REJECTED, ${low.error}`}`);
    tx("fulfill below minimum", low);

    out("c) nobody delivers in time, so the buyer takes the budget back");
    const req = await agent.getRequest(strict.requestId);
    const waitMs = Math.max(0, Number(BigInt(req.deadline_ns) / 1_000_000n) - Date.now()) + 5000;
    out(`   waiting about ${Math.ceil(waitMs / 1000)} seconds for the deadline`);
    await sleep(waitMs);
    let refund = await agent.refund(strict.requestId);
    for (let i = 0; !refund.ok && /not passed yet/.test(refund.error ?? "") && i < 6; i++) {
      await sleep(5000);
      refund = await agent.refund(strict.requestId);
    }
    out(`   result: ${refund.ok ? `REFUNDED ${target.price_near} NEAR to ${env.buyer.accountId}` : `refund failed, ${refund.error}`}`);
    tx("refund after deadline", refund);
    out(`   request #${strict.requestId} status: ${(await agent.getRequest(strict.requestId)).status}`);

    section("Summary");
    out(`transactions: ${txRecord.length}, rejected on purpose: ${txRecord.filter((t) => !t.ok).length}`);
    if (network === "testnet") {
      out(`contract: ${explorerAccount(network, env.market.accountId)}`);
    }
  } finally {
    await env.stop();
  }

  mkdirSync(`${root}demo-output`, { recursive: true });
  writeFileSync(`${root}demo-output/demo-${network}.log`, lines.join("\n") + "\n");
  writeFileSync(`${root}demo-output/demo-${network}-txs.json`, JSON.stringify(txRecord, null, 2) + "\n");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
