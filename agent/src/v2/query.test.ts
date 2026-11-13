import assert from 'node:assert/strict';
import test from 'node:test';
import { formatQuery, parseQuery, QueryError } from './query.ts';

const errors: [string, string][] = [
  ['', 'query is empty'], ['  ', 'query is empty'], ['a'.repeat(257), 'query is longer than 256 characters'],
  ['AND a', 'expected a term'], ['a OR', 'expected a term'], ['a AND OR b', 'expected a term'],
  ['(a', 'missing closing parenthesis'], ['a)', 'unexpected )'], [')', 'unexpected )'],
  ['a b', 'missing AND or OR between terms'], ['a(b)', 'missing AND or OR between terms'],
  ['(a b)', 'missing AND or OR between terms'], ['NOT a', 'NOT is not supported'],
  ['a and not b', 'NOT is not supported'], ['a*', 'wildcards are not supported'],
  ['"a?"', 'wildcards are not supported'], ['a,b', 'use OR between terms, not a comma'],
  ['"abc', 'unterminated quote'], ['"   "', 'empty term'], ['---', 'empty term'],
  [Array.from({ length: 17 }, (_, i) => `a${i}`).join(' OR '), 'more than 16 groups'],
  ['(a OR b OR c OR d OR e) AND (f OR g OR h OR i)', 'more than 16 groups'],
  [Array.from({ length: 9 }, (_, i) => `a${i}`).join(' AND '), 'more than 8 terms'],
];
for (const [input, message] of errors) {
  test(`QueryError: ${message} (${JSON.stringify(input)})`, () => {
    assert.throws(() => parseQuery(input), error => error instanceof QueryError && error.message.includes(message));
  });
}
test('canonical format, operator precedence, phrases and round trips', () => {
  const cases = [
    ['NVIDIA OR (Clarity AND Act)', 'nvidia OR (clarity AND act)'],
    ['(A OR B) AND C', '(a AND c) OR (b AND c)'],
    ['A OR a', 'a'],
    ['A AND a', 'a'],
    ['(A AND B) OR (b AND a)', 'a AND b'],
    ['a or b and c', 'a OR (b AND c)'],
    ['"Clarity Act" AND NVIDIA', '"clarity act" AND nvidia'],
    ['ＮＶＩＤＩＡ', 'nvidia'],
    ['((A))', 'a'],
    ['"not"', '"not"'],
    ['" Clarity   Act "', '"clarity act"'],
  ];
  for (const [input, expected] of cases) {
    const query = parseQuery(input);
    assert.equal(query.source, input);
    assert.equal(formatQuery(query), expected);
    assert.equal(formatQuery(parseQuery(expected)), expected);
  }
  assert.equal(parseQuery('(A OR B) AND C').groups.length, 2);
  assert.equal(parseQuery('A OR a').groups.length, 1);
});
test('limits allow exactly 256 characters, 16 groups and 8 distinct terms', () => {
  assert.equal(parseQuery('a'.repeat(256)).groups.length, 1);
  assert.equal(parseQuery(Array.from({ length: 16 }, (_, i) => `a${i}`).join(' OR ')).groups.length, 16);
  assert.equal(parseQuery(Array.from({ length: 8 }, (_, i) => `a${i}`).join(' AND ')).groups[0].length, 8);
  assert.equal(parseQuery(Array(17).fill('a').join(' OR ')).groups.length, 1);
  assert.equal(parseQuery(Array(9).fill('a').join(' AND ')).groups[0].length, 1);
});
