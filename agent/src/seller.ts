// Seller side: answers an open request with a signed fulfillment.
import type { Account } from "near-api-js";
import { call, type TxResult } from "./near.ts";
import { OralysOracle } from "./oracle.ts";
import type { FeedSignal } from "./feed.ts";

export class SellerOracle {
  constructor(
    readonly account: Account,
    readonly oracle: OralysOracle,
    readonly contractId: string,
  ) {}

  /** Signs and submits. `signWith` lets the demo and tests try a forged key. */
  async fulfill(requestId: string, signal: FeedSignal, opts: { signWith?: OralysOracle; scoreOverride?: number } = {}): Promise<TxResult> {
    const keyedHash = this.oracle.keyedHash(signal.transcript);
    const score = opts.scoreOverride ?? signal.quality_score;
    const signer = opts.signWith ?? this.oracle;
    const signature = signer.signFulfillment(this.contractId, requestId, signal.signal_id, keyedHash, score);
    return call(this.account, this.contractId, "fulfill", {
      request_id: requestId,
      signal_id: signal.signal_id,
      keyed_hash: keyedHash,
      quality_score: score,
      signature,
    });
  }
}
