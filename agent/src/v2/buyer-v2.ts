import { call, nearToYocto, view } from '../near.ts';
import { formatQuery, parseQuery } from './query.ts';

export class KeywordBuyer {
  constructor(private readonly account: Parameters<typeof call>[0],
    private readonly provider: Parameters<typeof view>[0], private readonly contractId: string) {}

  openRequest(o: { query: string; windowSeconds?: number; priceNear: string; budgetNear: string;
    minQuality: number; ttlSeconds: number }) {
    const query = formatQuery(parseQuery(o.query));
    return call(this.account, this.contractId, 'open_request', {
      query, window_seconds: o.windowSeconds ?? null, price_per_excerpt: nearToYocto(o.priceNear).toString(),
      min_quality: o.minQuality, ttl_seconds: o.ttlSeconds,
    }, { depositYocto: nearToYocto(o.budgetNear) });
  }
  getRequest<T = unknown>(requestId: string | number) {
    return view<T>(this.provider, this.contractId, 'get_request', { request_id: String(requestId) });
  }
  getPayouts<T = unknown>(requestId: string | number) {
    return view<T>(this.provider, this.contractId, 'get_payouts', { request_id: String(requestId) });
  }
  refund(requestId: string | number) {
    return call(this.account, this.contractId, 'refund', { request_id: String(requestId) });
  }
}
