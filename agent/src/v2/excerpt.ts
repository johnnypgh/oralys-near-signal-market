import { createHash } from 'node:crypto';
import type { Query } from './query.ts';
import type { ReplayedSegment } from './feed-v2.ts';
import { matchedGroups, splitSentences, termMatches, tokenize } from './matcher.ts';

export const MAX_EXCERPT_CHARS = 400;
export interface Excerpt {
  excerpt_id: string;
  segment_id: string;
  recording_id: string;
  label: string;
  text: string;
  excerpt_hash: string;
  recorded_at: number;
  quality_score: number;
  matched_groups: number[];
}
export function excerptHash(text: string): string {
  return createHash('sha256').update(text, 'utf8').digest('hex');
}
export function buildExcerpts(q: Query, seg: ReplayedSegment): Excerpt[] {
  const sentences = splitSentences(seg.text);
  const excerpts: Excerpt[] = [];
  for (let i = 0; i < sentences.length; i++) {
    const anchorTokens = tokenize(sentences[i]);
    let text = sentences.slice(Math.max(0, i - 1), i + 2).join(' ');
    if (text.length > MAX_EXCERPT_CHARS) text = sentences[i];
    if (text.length > MAX_EXCERPT_CHARS) {
      const boundary = text.lastIndexOf(' ', MAX_EXCERPT_CHARS);
      text = boundary < 0 ? '' : text.slice(0, boundary).trimEnd();
    }
    const groups = matchedGroups(q, text);
    if (!groups.some(index => q.groups[index].some(term => termMatches(term, anchorTokens)))) continue;
    excerpts.push({
      excerpt_id: `${seg.segment_id}-s${i}`, segment_id: seg.segment_id,
      recording_id: seg.recording_id, label: seg.label, text, excerpt_hash: excerptHash(text),
      recorded_at: seg.recorded_at_unix, quality_score: seg.quality_score, matched_groups: groups,
    });
    i += 2;
  }
  return excerpts;
}
export function selectExcerpts(q: Query, segs: ReplayedSegment[], o: {
  openedAtUnix: number; windowSeconds: number; nowUnix: number; minQuality: number;
  paid?: Set<string>; maxCount?: number;
}): Excerpt[] {
  const excerpts = segs.filter(seg => seg.recorded_at_unix >= o.openedAtUnix - o.windowSeconds &&
    seg.recorded_at_unix <= o.nowUnix && seg.quality_score >= o.minQuality)
    .flatMap(seg => buildExcerpts(q, seg)).filter(excerpt => !o.paid?.has(excerpt.excerpt_id))
    .sort((a, b) => a.recorded_at - b.recorded_at || (a.excerpt_id < b.excerpt_id ? -1 : a.excerpt_id > b.excerpt_id ? 1 : 0));
  return excerpts.slice(0, o.maxCount === undefined ? undefined : Math.max(0, o.maxCount));
}
