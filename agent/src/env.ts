// Sets up accounts and the market contract on either a local sandbox or testnet.
import { existsSync, mkdirSync, readFileSync, writeFileSync, chmodSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { Account, JsonRpcProvider, KeyPair, type KeyPairString } from "near-api-js";
import { call, nearToYocto, view, type Network, type TxResult } from "./near.ts";

export const DEFAULT_WASM = new URL("../../contract/target/near/oralys_signal_market.wasm", import.meta.url).pathname;

export interface MarketEnv {
  network: Network;
  provider: JsonRpcProvider;
  root: Account;
  market: Account;
  buyer: Account;
  seller: Account;
  setupTxs: Array<{ label: string; hash: string }>;
  stop: () => Promise<void>;
}

type Log = (msg: string) => void;

async function accountExists(provider: JsonRpcProvider, id: string): Promise<boolean> {
  try {
    await new Account(id, provider).getState();
    return true;
  } catch {
    return false;
  }
}

function txHash(res: any): string {
  return res?.transaction?.hash ?? res?.transaction_outcome?.id;
}

// ---------- local sandbox ----------

export async function startSandboxEnv(log: Log = () => {}): Promise<MarketEnv & { sandboxHome: string }> {
  const { Sandbox, DEFAULT_ACCOUNT_ID, DEFAULT_PRIVATE_KEY } = await import("near-sandbox");
  const sandbox = await Sandbox.start({});
  log(`local sandbox running at ${sandbox.rpcUrl}`);
  const provider = new JsonRpcProvider({ url: sandbox.rpcUrl });
  // The sandbox genesis account uses a well known public test key shipped with near-sandbox.
  const root = new Account(DEFAULT_ACCOUNT_ID, provider, DEFAULT_PRIVATE_KEY as KeyPairString);
  const setupTxs: MarketEnv["setupTxs"] = [];
  const mk = async (prefix: string, near: string) => {
    const kp = KeyPair.fromRandom("ed25519");
    const id = `${prefix}.${DEFAULT_ACCOUNT_ID}`;
    const res = await root.createSubAccount({ accountOrPrefix: prefix, publicKey: kp.getPublicKey(), nearToTransfer: nearToYocto(near) });
    setupTxs.push({ label: `create ${id}`, hash: txHash(res) });
    return new Account(id, provider, kp.toString() as KeyPairString);
  };
  const market = await mk("market", "5");
  const buyer = await mk("buyer", "5");
  const seller = await mk("seller", "1");
  return {
    network: "sandbox",
    provider,
    root,
    market,
    buyer,
    seller,
    setupTxs,
    sandboxHome: sandbox.homeDir,
    stop: () => sandbox.tearDown(),
  };
}

// ---------- testnet ----------

const CRED_DIR = join(homedir(), ".near-credentials", "testnet");

function readCredential(accountId: string): KeyPairString | undefined {
  const p = join(CRED_DIR, `${accountId}.json`);
  if (!existsSync(p)) return undefined;
  const j = JSON.parse(readFileSync(p, "utf8"));
  return (j.private_key ?? j.secret_key) as KeyPairString;
}

function writeCredential(accountId: string, kp: KeyPair): void {
  mkdirSync(CRED_DIR, { recursive: true });
  const p = join(CRED_DIR, `${accountId}.json`);
  writeFileSync(p, JSON.stringify({ account_id: accountId, public_key: kp.getPublicKey().toString(), private_key: kp.toString() }));
  chmodSync(p, 0o600);
}

export async function testnetEnv(rootId: string, rpcUrl: string, log: Log = () => {}): Promise<MarketEnv> {
  const provider = new JsonRpcProvider({ url: rpcUrl });
  const rootKey = readCredential(rootId);
  if (!rootKey) throw new Error(`no key for ${rootId} in ${CRED_DIR}`);
  const root = new Account(rootId, provider, rootKey);
  const setupTxs: MarketEnv["setupTxs"] = [];
  const sub = async (prefix: string, near: string) => {
    const id = `${prefix}.${rootId}`;
    const existing = readCredential(id);
    if (existing && (await accountExists(provider, id))) {
      log(`reusing ${id}`);
      return new Account(id, provider, existing);
    }
    const kp = KeyPair.fromRandom("ed25519");
    writeCredential(id, kp); // saved before the tx so a key is never lost
    const res = await root.createSubAccount({ accountOrPrefix: prefix, publicKey: kp.getPublicKey(), nearToTransfer: nearToYocto(near) });
    setupTxs.push({ label: `create ${id}`, hash: txHash(res) });
    log(`created ${id}`);
    return new Account(id, provider, kp.toString() as KeyPairString);
  };
  const market = await sub("market", process.env.MARKET_FUNDING_NEAR ?? "3");
  const buyer = await sub("buyer", process.env.BUYER_FUNDING_NEAR ?? "1");
  const seller = await sub("seller", process.env.SELLER_FUNDING_NEAR ?? "0.2");
  return { network: "testnet", provider, root, market, buyer, seller, setupTxs, stop: async () => {} };
}

// ---------- contract ----------

export async function deployMarket(
  env: MarketEnv,
  signerPublicKey: string,
  wasm: Uint8Array,
  log: Log = () => {},
): Promise<{ deployTx?: string; initTx?: TxResult }> {
  const res = await env.market.deployContract(wasm);
  const deployTx = txHash(res);
  env.setupTxs.push({ label: `deploy contract to ${env.market.accountId}`, hash: deployTx });
  let initialized = false;
  try {
    await view(env.provider, env.market.accountId, "get_config");
    initialized = true;
  } catch {
    initialized = false;
  }
  let initTx: TxResult;
  if (!initialized) {
    initTx = await call(env.market, env.market.accountId, "new", {
      owner: env.root.accountId,
      seller: env.seller.accountId,
      signer_public_key: signerPublicKey,
    });
    env.setupTxs.push({ label: "init market", hash: initTx.hash });
  } else {
    log("contract already initialized, refreshing the signer key");
    initTx = await call(env.root, env.market.accountId, "set_signer", {
      seller: env.seller.accountId,
      signer_public_key: signerPublicKey,
    });
    env.setupTxs.push({ label: "set_signer", hash: initTx.hash });
  }
  if (!initTx.ok) throw new Error(`market init failed: ${initTx.error}`);
  return { deployTx, initTx };
}
