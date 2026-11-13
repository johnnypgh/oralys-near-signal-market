import { call } from '../near.ts';
import type { Excerpt } from './excerpt.ts';
import { OralysOracleV2 } from './oracle-v2.ts';

export class KeywordSeller {
  constructor(private readonly account: Parameters<typeof call>[0], private readonly contractId: string,
    private readonly oracle: OralysOracleV2) {}

  fulfillExcerpt(requestId: string | number, excerpt: Excerpt, opts: {
    signWith?: OralysOracleV2; scoreOverride?: number; recordedAtOverride?: number;
  } = {}) {
    const score = opts.scoreOverride ?? excerpt.quality_score;
    const recordedAt = opts.recordedAtOverride ?? excerpt.recorded_at;
    const signature = (opts.signWith ?? this.oracle).signExcerpt(this.contractId, requestId,
      excerpt.excerpt_id, excerpt.excerpt_hash, recordedAt, score);
    return call(this.account, this.contractId, 'fulfill_excerpt', {
      request_id: String(requestId), excerpt_id: excerpt.excerpt_id, excerpt_hash: excerpt.excerpt_hash,
      recorded_at: String(recordedAt), quality_score: score, signature,
    });
  }
}
