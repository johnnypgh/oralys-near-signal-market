export interface Term { text: string; tokens: string[]; phrase: boolean }
export interface Query { source: string; groups: Term[][] }
export class QueryError extends Error {}

type Token = { kind: 'term'; term: Term } | { kind: 'AND' | 'OR' | '(' | ')' };
const normalize = (text: string) => text.normalize('NFKC').toLowerCase();
const termKey = (term: Term) => JSON.stringify(term.tokens);

function uniqueGroups(groups: Term[][]): Term[][] {
  const result = new Map<string, Term[]>();
  for (const group of groups) {
    const terms = [...new Map(group.map(term => [termKey(term), term])).values()];
    if (terms.length > 8) throw new QueryError('more than 8 terms');
    const key = JSON.stringify(terms.map(termKey).sort());
    if (!result.has(key)) result.set(key, terms);
  }
  if (result.size > 16) throw new QueryError('more than 16 groups');
  return [...result.values()];
}

export function parseQuery(input: string): Query {
  if (!input.trim()) throw new QueryError('query is empty');
  if (input.length > 256) throw new QueryError('query is longer than 256 characters');
  const source = normalize(input);
  if (/[*?]/u.test(source)) throw new QueryError('wildcards are not supported');
  if (source.includes(',')) throw new QueryError('use OR between terms, not a comma');
  const lexed: Token[] = [];
  let pos = 0;
  while (pos < source.length) {
    const char = source[pos];
    if (/\s/u.test(char)) { pos++; continue; }
    if (char === '(' || char === ')') { lexed.push({ kind: char }); pos++; continue; }
    const phrase = char === '"';
    let raw: string;
    if (phrase) {
      const end = source.indexOf('"', pos + 1);
      if (end < 0) throw new QueryError('unterminated quote');
      raw = source.slice(pos + 1, end); pos = end + 1;
    } else {
      const start = pos;
      while (pos < source.length && !/[\s()"]/u.test(source[pos])) pos++;
      raw = source.slice(start, pos);
      if (raw === 'not') throw new QueryError('NOT is not supported');
      if (raw === 'and' || raw === 'or') {
        lexed.push({ kind: raw.toUpperCase() as 'AND' | 'OR' }); continue;
      }
    }
    const tokens = raw.match(/[\p{L}\p{N}]+/gu) ?? [];
    if (!tokens.length) throw new QueryError('empty term');
    lexed.push({ kind: 'term', term: { text: tokens.join(' '), tokens, phrase: phrase || tokens.length > 1 } });
  }
  let cursor = 0;
  const peek = () => lexed[cursor]?.kind;
  function atom(): Term[][] {
    const token = lexed[cursor++];
    if (!token) throw new QueryError('expected a term');
    if (token.kind === 'term') return [[token.term]];
    if (token.kind === ')') throw new QueryError('unexpected )');
    if (token.kind !== '(') throw new QueryError('expected a term');
    const groups = expr();
    if (peek() !== ')') {
      if (peek() === 'term' || peek() === '(') throw new QueryError('missing AND or OR between terms');
      throw new QueryError('missing closing parenthesis');
    }
    cursor++;
    return groups;
  }
  function and(): Term[][] {
    let groups = atom();
    while (peek() === 'AND') {
      cursor++;
      const right = atom();
      groups = uniqueGroups(groups.flatMap(left => right.map(group => [...left, ...group])));
    }
    return groups;
  }
  function expr(): Term[][] {
    let groups = and();
    while (peek() === 'OR') { cursor++; groups = uniqueGroups([...groups, ...and()]); }
    return groups;
  }
  const groups = uniqueGroups(expr());
  if (peek() === ')') throw new QueryError('unexpected )');
  if (peek()) throw new QueryError('missing AND or OR between terms');
  return { source: input, groups };
}

export function formatQuery(q: Query): string {
  return q.groups.map(group => {
    const text = group.map(term => term.phrase ? `"${term.text}"` : term.text).join(' AND ');
    return group.length > 1 && q.groups.length > 1 ? `(${text})` : text;
  }).join(' OR ');
}
