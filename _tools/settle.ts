// Stage 03: settle the buy decisions on the market contract and write tx receipts.
//
//   npx tsx _tools/settle.ts --network sandbox     fresh local sandbox, deploys the contract first
//   NEAR_ACCOUNT_ID=<you>.testnet npx tsx _tools/settle.ts --network testnet
//
// The seller side is simulated by the sample oracle in agent/src/seller.ts, which signs
// SAMPLE DATA fulfillments with a locally generated key kept in .keys/ (gitignored).
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { startSandboxEnv, testnetEnv, deployMarket, DEFAULT_WASM, type MarketEnv } from "../agent/src/env.ts";
import { OralysOracle } from "../agent/src/oracle.ts";
import { BuyerAgent } from "../agent/src/buyer-agent.ts";
import { SellerOracle } from "../agent/src/seller.ts";
import { explorerTx, view, type Network } from "../agent/src/near.ts";
import type { FeedSignal } from "../agent/src/feed.ts";

const root = new URL("..", import.meta.url).pathname;
const arg = (name: string) => (process.argv.includes(name) ? process.argv[process.argv.indexOf(name) + 1] : undefined);
const network: Network = arg("--network") === "testnet" ? "testnet" : "sandbox";
const OUT = "stages/03_settle/output/receipts.json";

async function main() {
  const decisions = JSON.parse(readFileSync(`${root}stages/02_evaluate/output/decisions.json`, "utf8"));
  const feed = JSON.parse(readFileSync(`${root}stages/01_intake/output/feed.json`, "utf8"));
  const policy = JSON.parse(readFileSync(`${root}_shared/policy.json`, "utf8"));
  const byId: Record<string, FeedSignal> = Object.fromEntries(feed.signals.map((s: FeedSignal) => [s.signal_id, s]));

  let env: MarketEnv;
  if (network === "sandbox") {
    env = await startSandboxEnv(console.log);
  } else {
    const id = process.env.NEAR_ACCOUNT_ID;
    if (!id) throw new Error("set NEAR_ACCOUNT_ID");
    env = await testnetEnv(id, process.env.NEAR_RPC_URL ?? "https://test.rpc.fastnear.com", console.log);
  }
  const receipts: any[] = [];
  try {
    const oracle = OralysOracle.loadOrCreate(`${root}.keys/oracle-${network}.json`);
    let deployed = false;
    try {
      const cfg: any = await view(env.provider, env.market.accountId, "get_config");
      deployed = cfg.signer_public_key === oracle.publicKey;
    } catch {
      deployed = false;
    }
    if (!deployed) await deployMarket(env, oracle.publicKey, readFileSync(DEFAULT_WASM), console.log);

    const agent = new BuyerAgent({
      account: env.buyer,
      provider: env.provider,
      contractId: env.market.accountId,
      budgetNear: policy.budget_near,
      minQuality: policy.min_quality,
      ttlSeconds: policy.ttl_seconds,
    });
    const seller = new SellerOracle(env.seller, oracle, env.market.accountId);

    for (const d of decisions.decisions) {
      if (!d.buy) continue;
      const s = byId[d.signal_id];
      const opened = await agent.openRequest(s);
      const f = await seller.fulfill(opened.requestId, s);
      const req = await agent.getRequest(opened.requestId);
      const ful: any = await agent.getFulfillment(opened.requestId);
      const r = {
        signal_id: s.signal_id,
        request_id: opened.requestId,
        price_near: s.price_near,
        status: req.status,
        quality_score_on_chain: ful?.quality_score ?? null,
        keyed_hash: ful?.keyed_hash ?? null,
        open_tx: opened.tx.hash,
        fulfill_tx: f.hash,
        fulfill_error: f.ok ? null : f.error,
        links: network === "testnet" ? [explorerTx(network, opened.tx.hash), explorerTx(network, f.hash)] : [],
      };
      receipts.push(r);
      console.log(`${s.signal_id}: request #${r.request_id} ${r.status} open=${r.open_tx} fulfill=${r.fulfill_tx}`);
    }
    const out = {
      network,
      note: "SAMPLE DATA run. Seller side is the sample oracle in this repo.",
      contract: env.market.accountId,
      buyer: env.buyer.accountId,
      seller: env.seller.accountId,
      signer_public_key: oracle.publicKey,
      setup_txs: env.setupTxs,
      receipts,
    };
    mkdirSync(`${root}stages/03_settle/output`, { recursive: true });
    writeFileSync(`${root}${OUT}`, JSON.stringify(out, null, 2) + "\n");
    console.log(`wrote ${OUT} (${receipts.length} receipts)`);
  } finally {
    await env.stop();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
