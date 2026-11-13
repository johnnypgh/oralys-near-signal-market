import type { Query, Term } from './query.ts';

export function tokenize(text: string): string[] {
  return text.normalize('NFKC').toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [];
}
export function splitSentences(text: string): string[] {
  return text.trim().split(/(?<=[.!?])\s+/u).filter(Boolean);
}
export function termMatches(term: Term, tokens: string[]): boolean {
  return term.tokens.length > 0 && tokens.some((_, start) =>
    term.tokens.every((token, offset) => tokens[start + offset] === token));
}
export function groupMatches(group: Term[], text: string): boolean {
  const tokens = tokenize(text);
  return group.length > 0 && group.every(term => termMatches(term, tokens));
}
export function matchedGroups(q: Query, text: string): number[] {
  return q.groups.flatMap((group, index) => groupMatches(group, text) ? [index] : []);
}
export function matches(q: Query, text: string): boolean {
  return matchedGroups(q, text).length > 0;
}
