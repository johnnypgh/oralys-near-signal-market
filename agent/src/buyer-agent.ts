// Buyer agent: holds a budget and a quality bar, reads the signal feed, pays
// only for signals that clear the bar, and checks delivery on chain.
import type { Account, JsonRpcProvider } from "near-api-js";
import { call, nearToYocto, view, type TxResult } from "./near.ts";
import type { FeedSignal } from "./feed.ts";

export interface BuyerAgentOptions {
  account: Account;
  provider: JsonRpcProvider;
  contractId: string;
  budgetNear: string;
  minQuality: number;
  ttlSeconds: number;
  topics?: string[];
}

export type Decision = { buy: true; reason: string } | { buy: false; reason: string };

export interface OpenedRequest {
  requestId: string;
  signal: FeedSignal;
  tx: TxResult;
}

export class BuyerAgent {
  readonly opts: BuyerAgentOptions;
  private remaining: bigint;

  constructor(opts: BuyerAgentOptions) {
    if (opts.minQuality < 0 || opts.minQuality > 100) throw new Error("minQuality must be 0 to 100");
    this.opts = opts;
    this.remaining = nearToYocto(opts.budgetNear);
  }

  get accountId(): string {
    return this.opts.account.accountId;
  }

  get remainingYocto(): bigint {
    return this.remaining;
  }

  evaluate(signal: FeedSignal): Decision {
    if (this.opts.topics && !this.opts.topics.includes(signal.topic)) {
      return { buy: false, reason: `topic ${signal.topic} not wanted` };
    }
    if (signal.quality_score < this.opts.minQuality) {
      return { buy: false, reason: `quality ${signal.quality_score} is below my minimum of ${this.opts.minQuality}` };
    }
    const price = nearToYocto(signal.price_near);
    if (price > this.remaining) {
      return { buy: false, reason: `price ${signal.price_near} NEAR is more than my remaining budget` };
    }
    return { buy: true, reason: `quality ${signal.quality_score} meets my minimum of ${this.opts.minQuality}` };
  }

  async openRequest(signal: FeedSignal, overrides: { minQuality?: number; ttlSeconds?: number } = {}): Promise<OpenedRequest> {
    const price = nearToYocto(signal.price_near);
    if (price > this.remaining) throw new Error("not enough budget left for this request");
    const tx = await call(
      this.opts.account,
      this.opts.contractId,
      "open_request",
      {
        min_quality: overrides.minQuality ?? this.opts.minQuality,
        ttl_seconds: overrides.ttlSeconds ?? this.opts.ttlSeconds,
        topic: `${signal.topic}:${signal.signal_id}`,
      },
      { depositYocto: price },
    );
    if (!tx.ok) throw new Error(`open_request failed: ${tx.error}`);
    this.remaining -= price;
    return { requestId: String(tx.value), signal, tx };
  }

  async getRequest(requestId: string): Promise<any> {
    return view(this.opts.provider, this.opts.contractId, "get_request", { request_id: requestId });
  }

  async getFulfillment(requestId: string): Promise<any> {
    return view(this.opts.provider, this.opts.contractId, "get_fulfillment", { request_id: requestId });
  }

  async refund(requestId: string): Promise<TxResult> {
    return call(this.opts.account, this.opts.contractId, "refund", { request_id: requestId });
  }
}
