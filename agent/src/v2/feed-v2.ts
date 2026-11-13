import { readFileSync } from 'node:fs';

export interface KeywordSegment {
  segment_id: string;
  recording_id: string;
  label: string;
  event: string;
  recorded_at: string;
  quality_score: number;
  text: string;
}
export interface KeywordFeed {
  notice: string;
  feed: string;
  schema_version: number;
  replay_anchor: string;
  segments: KeywordSegment[];
}
export interface ReplayedSegment extends KeywordSegment { recorded_at_unix: number }

function unix(value: unknown, field: string): number {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/u.test(value)) {
    throw new Error(`bad ${field}`);
  }
  const millis = Date.parse(value);
  if (!Number.isFinite(millis) || new Date(millis).toISOString() !== value.replace('Z', '.000Z')) {
    throw new Error(`bad ${field}`);
  }
  return millis / 1000;
}
export function loadKeywordFeed(path: string): KeywordFeed {
  const feed = JSON.parse(readFileSync(path, 'utf8')) as KeywordFeed;
  if (typeof feed?.notice !== 'string' || !feed.notice.startsWith('SAMPLE DATA')) {
    throw new Error('feed must be labeled SAMPLE DATA');
  }
  unix(feed.replay_anchor, 'replay_anchor');
  if (!Array.isArray(feed.segments)) throw new Error('feed must contain segments');
  const ids = new Set<string>();
  for (const segment of feed.segments) {
    if (!segment || segment.label !== 'SAMPLE DATA') throw new Error('segment is not labeled SAMPLE DATA');
    if (typeof segment.text !== 'string' || !segment.text.startsWith('SAMPLE DATA.')) {
      throw new Error('segment text must start with SAMPLE DATA.');
    }
    if (typeof segment.segment_id !== 'string' || !/^[a-zA-Z0-9_-]+$/u.test(segment.segment_id) || ids.has(segment.segment_id)) {
      throw new Error('bad segment_id');
    }
    ids.add(segment.segment_id);
    unix(segment.recorded_at, 'recorded_at');
  }
  return feed;
}
export function replayFeed(feed: KeywordFeed, anchorUnix: number): ReplayedSegment[] {
  if (!Number.isSafeInteger(anchorUnix)) throw new Error('bad anchorUnix');
  const shift = anchorUnix - unix(feed.replay_anchor, 'replay_anchor');
  return feed.segments.map(segment => ({ ...segment, recorded_at_unix: unix(segment.recorded_at, 'recorded_at') + shift }));
}
