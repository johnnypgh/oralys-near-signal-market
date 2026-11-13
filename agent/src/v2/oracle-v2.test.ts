import assert from 'node:assert/strict';
import { createPublicKey, verify } from 'node:crypto';
import test from 'node:test';
import { baseDecode } from 'near-api-js';
import { OralysOracleV2 } from './oracle-v2.ts';

test('exact v2 signing message binds all fields in order', () => {
  assert.equal(OralysOracleV2.signingMessage('market.test.near', '42', 'sd-r3-02-s2', 'ab'.repeat(32), 1794581700, 79),
    `oralys-signal-v2|market.test.near|42|sd-r3-02-s2|${'ab'.repeat(32)}|1794581700|79`);
  assert.equal(OralysOracleV2.signingMessage('market', 42, 'sd', 'hash', '123', 70),
    'oralys-signal-v2|market|42|sd|hash|123|70');
});
test('throwaway seed only, hex signature verifies with node:crypto and rejects changed fields', () => {
  const keys = OralysOracleV2.generateKeys();
  assert.deepEqual(Object.keys(keys), ['seedHex']);
  const oracle = new OralysOracleV2(keys);
  assert.match(oracle.publicKey, /^ed25519:/u);
  const publicKey = createPublicKey({
    key: Buffer.concat([Buffer.from('302a300506032b6570032100', 'hex'), Buffer.from(baseDecode(oracle.publicKey.slice(8)))]),
    format: 'der', type: 'spki',
  });
  const args = ['market.test.near', '42', 'sd-r3-02-s2', 'ab'.repeat(32), 1794581700, 79] as const;
  const signature = oracle.signExcerpt(...args);
  assert.match(signature, /^[0-9a-f]{128}$/u);
  const valid = (message: string) => verify(null, Buffer.from(message, 'utf8'), publicKey, Buffer.from(signature, 'hex'));
  const message = OralysOracleV2.signingMessage(...args);
  assert.equal(valid(message), true);
  const fields = message.split('|');
  fields.forEach((_, i) => {
    const changed = [...fields]; changed[i] += '1';
    assert.equal(valid(changed.join('|')), false);
  });
  assert.equal(new OralysOracleV2(keys).signExcerpt(...args), signature);
  const other = new OralysOracleV2(OralysOracleV2.generateKeys());
  assert.equal(verify(null, Buffer.from(message), publicKey, Buffer.from(other.signExcerpt(...args), 'hex')), false);
});
test('malformed seeds are rejected without exposing seed contents', () => {
  for (const seedHex of ['', '00'.repeat(31), '00'.repeat(33), 'zz'.repeat(32)]) {
    assert.throws(() => new OralysOracleV2({ seedHex }), { message: 'oracle seed must be 32 bytes' });
  }
});
