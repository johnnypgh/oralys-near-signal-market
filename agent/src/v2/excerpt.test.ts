import assert from 'node:assert/strict';
import fs from 'node:fs';
import { syncBuiltinESMExports } from 'node:module';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { buildExcerpts, excerptHash, MAX_EXCERPT_CHARS, selectExcerpts } from './excerpt.ts';
import { loadKeywordFeed, replayFeed, type ReplayedSegment } from './feed-v2.ts';
import { parseQuery } from './query.ts';

const fixturePath = fileURLToPath(new URL('../../../sample-data/keyword-feed.json', import.meta.url));
const feed = loadKeywordFeed(fixturePath);
const anchor = Date.parse(feed.replay_anchor) / 1000;
const segments = replayFeed(feed, anchor);
const query = parseQuery('NVIDIA OR (Clarity AND Act)');
const options = { openedAtUnix: anchor, windowSeconds: 3600, nowUnix: anchor, minQuality: 70 };
const expected = ['sd-r1-02-s2', 'sd-r2-01-s2', 'sd-r3-02-s2', 'sd-r3-02-s5'];
const ids = (items: ReturnType<typeof buildExcerpts>) => items.map(item => item.excerpt_id);
const synthetic = (text: string): ReplayedSegment => ({ ...segments[0], text: `SAMPLE DATA. ${text}`, recorded_at_unix: anchor });

test('fixture matches exactly at anchor, five minutes later and with a 7200 second window', () => {
  assert.deepEqual(ids(selectExcerpts(query, segments, options)), expected);
  assert.deepEqual(ids(selectExcerpts(query, segments, { ...options, nowUnix: anchor + 300 })), [...expected, 'sd-r4-01-s1']);
  assert.deepEqual(ids(selectExcerpts(query, segments, { ...options, windowSeconds: 7200 })), ['sd-r1-01-s1', ...expected]);
  assert.deepEqual(ids(selectExcerpts(query, segments, { ...options, windowSeconds: 7200, nowUnix: anchor + 300 })), ['sd-r1-01-s1', ...expected, 'sd-r4-01-s1']);
});
test('fixture separate anchors do not overlap and excerpts carry correct metadata and hashes', () => {
  const seg = segments.find(s => s.segment_id === 'sd-r3-02')!;
  const items = buildExcerpts(query, seg);
  assert.deepEqual(ids(items), ['sd-r3-02-s2', 'sd-r3-02-s5']);
  assert.equal(items[0].text, 'Host: Welcome back to the hardware panel. Speaker C: Our first cluster ran on NVIDIA cards. Speaker D: Power was the main cost.');
  assert.equal(items[1].text, 'Host: Cooling came up in every question. Speaker C: The next order is NVIDIA again, pending budget.');
  for (const e of items) {
    assert.equal(e.segment_id, seg.segment_id); assert.equal(e.recording_id, seg.recording_id);
    assert.equal(e.label, 'SAMPLE DATA'); assert.equal(e.recorded_at, seg.recorded_at_unix);
    assert.equal(e.quality_score, seg.quality_score); assert.equal(e.excerpt_hash, excerptHash(e.text));
    assert.deepEqual(e.matched_groups, [0]); assert.ok(e.text.length <= MAX_EXCERPT_CHARS);
  }
});
test('selection excludes paid excerpts, sorts ties by id and honors maxCount', () => {
  assert.deepEqual(ids(selectExcerpts(query, [...segments].reverse(), { ...options, paid: new Set([expected[0]]), maxCount: 2 })), expected.slice(1, 3));
  assert.deepEqual(selectExcerpts(query, segments, { ...options, maxCount: 0 }), []);
  const tied = ['sd-z', 'sd-a'].map(segment_id => ({ ...synthetic('NVIDIA.'), segment_id }));
  assert.deepEqual(ids(selectExcerpts(query, tied, options)), ['sd-a-s1', 'sd-z-s1']);
});
test('time and quality boundaries are inclusive and future and old segments are excluded', () => {
  const seg = synthetic('NVIDIA.');
  for (const recorded_at_unix of [anchor - 3600, anchor]) {
    assert.equal(selectExcerpts(query, [{ ...seg, recorded_at_unix, quality_score: 70 }], options).length, 1);
  }
  for (const recorded_at_unix of [anchor - 3601, anchor + 1]) {
    assert.equal(selectExcerpts(query, [{ ...seg, recorded_at_unix }], options).length, 0);
  }
  assert.equal(selectExcerpts(query, [{ ...seg, quality_score: 69 }], options).length, 0);
});
test('over 400 characters drops context first', () => {
  const items = buildExcerpts(query, synthetic(`${'context '.repeat(55)}done. NVIDIA wins. Next topic.`));
  assert.equal(items.length, 1); assert.equal(items[0].text, 'NVIDIA wins.');
  assert.equal(items[0].excerpt_id, 'sd-r1-01-s2');
});
test('overlong anchor cuts at a word boundary and keeps a surviving match', () => {
  const sentence = `NVIDIA ${'hardware '.repeat(60)}done.`;
  const items = buildExcerpts(query, synthetic(sentence));
  assert.equal(items.length, 1);
  assert.equal(items[0].text, sentence.slice(0, sentence.lastIndexOf(' ', 400)).trimEnd());
  assert.ok(items[0].text.length <= 400); assert.ok(items[0].text.endsWith('hardware'));
});
test('cut that loses match produces no excerpt, including AND group loss', () => {
  assert.deepEqual(buildExcerpts(query, synthetic(`${'hardware '.repeat(60)}NVIDIA.`)), []);
  assert.deepEqual(buildExcerpts(query, synthetic(`Clarity ${'hardware '.repeat(60)}Act.`)), []);
  assert.deepEqual(buildExcerpts(query, synthetic(`${'a'.repeat(410)} NVIDIA.`)), []);
});
test('400 character sentence is not cut', () => {
  const sentence = `NVIDIA ${'x'.repeat(392)}.`;
  assert.equal(sentence.length, 400);
  assert.equal(buildExcerpts(query, synthetic(sentence))[0].text, sentence);
});
test('anchor must contain a term of a satisfied group and AND cannot span separate excerpts', () => {
  assert.equal(buildExcerpts(query, synthetic('Context only. NVIDIA.'))[0].excerpt_id, 'sd-r1-01-s2');
  assert.deepEqual(buildExcerpts(parseQuery('Clarity AND Act'), synthetic('Clarity. First gap. Second gap. Act.')), []);
  assert.equal(buildExcerpts(query, synthetic('Clarity. Context. NVIDIA.'))[0].excerpt_id, 'sd-r1-01-s3');
});
test('sha256 known vector', () => {
  assert.equal(excerptHash('abc'), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
});
test('replay shifts timestamps without changing source segments', () => {
  const shifted = replayFeed(feed, anchor + 1234);
  assert.equal(shifted.length, 8);
  shifted.forEach((s, i) => {
    assert.equal(s.recorded_at_unix, segments[i].recorded_at_unix + 1234);
    assert.equal(s.recorded_at, feed.segments[i].recorded_at);
    assert.equal(s.text, feed.segments[i].text);
  });
  assert.equal('recorded_at_unix' in feed.segments[0], false);
  assert.throws(() => replayFeed(feed, NaN), /bad anchorUnix/);
});
test('feed rejects missing labels, unsafe ids and invalid dates without writing fixture files', t => {
  const cases: [((copy: typeof feed) => void), RegExp][] = [
    [copy => { delete (copy as Partial<typeof feed>).notice; }, /SAMPLE DATA/],
    [copy => { copy.segments[0].label = ''; }, /SAMPLE DATA/],
    [copy => { copy.segments[0].text = 'unlabeled'; }, /SAMPLE DATA/],
    [copy => { copy.segments[0].segment_id = ''; }, /bad segment_id/],
    [copy => { copy.segments[0].segment_id = '../bad'; }, /bad segment_id/],
    [copy => { copy.segments[0].segment_id = copy.segments[1].segment_id; }, /bad segment_id/],
    [copy => { copy.segments[0].recorded_at = 'bad'; }, /bad recorded_at/],
    [copy => { copy.segments[0].recorded_at = '2026-02-30T15:00:00Z'; }, /bad recorded_at/],
    [copy => { copy.replay_anchor = 'bad'; }, /bad replay_anchor/],
  ];
  for (const [mutate, message] of cases) {
    const copy = structuredClone(feed); mutate(copy);
    const mock = t.mock.method(fs, 'readFileSync', () => JSON.stringify(copy));
    syncBuiltinESMExports();
    try { assert.throws(() => loadKeywordFeed('unused-in-memory-fixture'), message); }
    finally { mock.mock.restore(); syncBuiltinESMExports(); }
  }
});
