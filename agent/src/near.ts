// Thin helpers over near-api-js v7 shared by the agent, the oracle, the demo and the tests.
import { Account, JsonRpcProvider, actions, type KeyPairString } from "near-api-js";

export const TGAS = 1_000_000_000_000n;
export const YOCTO_PER_NEAR = 10n ** 24n;

export type Network = "sandbox" | "testnet";

export interface TxResult {
  ok: boolean;
  hash: string;
  logs: string[];
  events: Array<{ event: string; data: unknown[] }>;
  error?: string;
  value?: unknown;
}

export function nearToYocto(near: string): bigint {
  const [whole, frac = ""] = near.split(".");
  return BigInt(whole) * YOCTO_PER_NEAR + BigInt((frac + "0".repeat(24)).slice(0, 24));
}

export function yoctoToNear(yocto: bigint | string, digits = 4): string {
  const y = BigInt(yocto);
  const whole = y / YOCTO_PER_NEAR;
  const frac = (y % YOCTO_PER_NEAR).toString().padStart(24, "0").slice(0, digits);
  return `${whole}.${frac}`;
}

export function explorerTx(network: Network, hash: string): string | undefined {
  return network === "testnet" ? `https://testnet.nearblocks.io/txns/${hash}` : undefined;
}

export function explorerAccount(network: Network, accountId: string): string | undefined {
  return network === "testnet" ? `https://testnet.nearblocks.io/address/${accountId}` : undefined;
}

export function makeAccount(accountId: string, provider: JsonRpcProvider, secretKey?: KeyPairString): Account {
  return new Account(accountId, provider, secretKey);
}

function extractPanic(status: unknown): string | undefined {
  const s = JSON.stringify(status ?? "");
  const m = s.match(/Smart contract panicked: ([^"\\]+)/);
  if (m) return m[1];
  if (s.includes("Failure")) return s;
  return undefined;
}

/** Sends a function call and never throws on contract failure, so callers can show rejections. */
export async function call(
  signer: Account,
  contractId: string,
  methodName: string,
  args: Record<string, unknown>,
  opts: { depositYocto?: bigint; gasTgas?: bigint } = {},
): Promise<TxResult> {
  const res: any = await signer.signAndSendTransaction({
    receiverId: contractId,
    actions: [
      actions.functionCall(methodName, args, (opts.gasTgas ?? 50n) * TGAS, opts.depositYocto ?? 0n),
    ],
    throwOnFailure: false,
    waitUntil: "FINAL",
  });
  const hash: string = res.transaction?.hash ?? res.transaction_outcome?.id;
  const outcomes: any[] = [res.transaction_outcome, ...(res.receipts_outcome ?? [])];
  const logs = outcomes.flatMap((o) => o?.outcome?.logs ?? []);
  const events = logs
    .filter((l: string) => l.startsWith("EVENT_JSON:"))
    .map((l: string) => JSON.parse(l.slice("EVENT_JSON:".length)));
  const receiptFailure = (res.receipts_outcome ?? [])
    .map((o: any) => extractPanic(o?.outcome?.status))
    .find((x: string | undefined) => x);
  const topFailure = res.status && typeof res.status === "object" && "Failure" in res.status;
  const error = topFailure ? extractPanic(res.status) ?? JSON.stringify(res.status) : receiptFailure;
  let value: unknown;
  if (res.status?.SuccessValue) {
    try {
      value = JSON.parse(Buffer.from(res.status.SuccessValue, "base64").toString());
    } catch {
      value = undefined;
    }
  }
  return { ok: !error, hash, logs, events, error, value };
}

export async function view<T>(
  provider: JsonRpcProvider,
  contractId: string,
  method: string,
  args: Record<string, unknown> = {},
): Promise<T> {
  return (await provider.callFunction<any>({ contractId, method, args, finality: "final" } as any)) as T;
}

export async function balance(provider: JsonRpcProvider, accountId: string): Promise<bigint> {
  const a = new Account(accountId, provider);
  return a.getBalance();
}
