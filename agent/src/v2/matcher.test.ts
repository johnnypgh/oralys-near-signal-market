import assert from 'node:assert/strict';
import test from 'node:test';
import { parseQuery } from './query.ts';
import { groupMatches, matchedGroups, matches, splitSentences, termMatches, tokenize } from './matcher.ts';

test('NFKC and Unicode letter and digit runs', () => {
  assert.deepEqual(tokenize("ＮＶＩＤＩＡ's GPU42, café １２!"), ['nvidia', 's', 'gpu42', 'café', '12']);
  assert.deepEqual(tokenize('...'), []);
});
test('whole token matching excludes prefixes', () => {
  const act = parseQuery('Act');
  assert.equal(matches(act, 'Actually, actions matter.'), false);
  assert.equal(matches(act, 'The ACT passed.'), true);
  for (const text of ["NVIDIA's chips", 'ＮＶＩＤＩＡ cards', 'nViDiA']) {
    assert.equal(matches(parseQuery('nvidia'), text), true);
  }
});
test('phrase tokens must be contiguous', () => {
  const q = parseQuery('"Clarity Act"');
  assert.equal(matches(q, 'Clarity-Act'), true);
  assert.equal(matches(q, 'Clarity of the Act'), false);
  assert.equal(matches(q, 'Act Clarity'), false);
  assert.equal(termMatches(q.groups[0][0], ['clarity']), false);
  assert.equal(termMatches({ text: '', tokens: [], phrase: true }, ['a']), false);
});
test('AND groups and returned OR group indexes', () => {
  const q = parseQuery('NVIDIA OR (Clarity AND Act)');
  assert.deepEqual(matchedGroups(q, 'NVIDIA. Clarity. Act.'), [0, 1]);
  assert.deepEqual(matchedGroups(q, 'Clarity on fees. Actually, yes.'), []);
  assert.equal(groupMatches(q.groups[1], 'Act then Clarity'), true);
  assert.equal(groupMatches(q.groups[1], 'Clarity only'), false);
  assert.equal(groupMatches([], 'SAMPLE DATA.'), false);
});
test('sentence split preserves punctuation and ignores empty edges', () => {
  assert.deepEqual(splitSentences('  SAMPLE DATA. One!\nTwo? Three.  '), ['SAMPLE DATA.', 'One!', 'Two?', 'Three.']);
  assert.deepEqual(splitSentences('One.Two!Three?Four'), ['One.Two!Three?Four']);
  assert.deepEqual(splitSentences(' \n '), []);
});
