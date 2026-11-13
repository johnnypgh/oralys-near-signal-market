import { readFileSync } from "node:fs";

export interface FeedSignal {
  signal_id: string;
  label: string;
  topic: string;
  title: string;
  quality_score: number;
  price_near: string;
  transcript: string;
}

export interface SignalFeed {
  notice: string;
  feed: string;
  signals: FeedSignal[];
}

export function loadFeed(path: string): SignalFeed {
  const feed = JSON.parse(readFileSync(path, "utf8")) as SignalFeed;
  if (!feed.notice?.startsWith("SAMPLE DATA")) throw new Error("feed must be labeled SAMPLE DATA");
  for (const s of feed.signals) {
    if (s.label !== "SAMPLE DATA") throw new Error(`signal ${s.signal_id} is not labeled SAMPLE DATA`);
  }
  return feed;
}
