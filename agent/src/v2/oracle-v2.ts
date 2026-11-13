import { createPrivateKey, createPublicKey, generateKeyPairSync, sign } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { baseEncode } from 'near-api-js';

export interface OracleKeysV2 { seedHex: string }
export const SIGNING_DOMAIN = 'oralys-signal-v2';
const PREFIX = Buffer.from('302e020100300506032b657004220420', 'hex');

export class OralysOracleV2 {
  private readonly privateKey;
  readonly publicKey: string;

  constructor(keys: OracleKeysV2) {
    if (!/^[0-9a-fA-F]{64}$/u.test(keys.seedHex)) throw new Error('oracle seed must be 32 bytes');
    this.privateKey = createPrivateKey({
      key: Buffer.concat([PREFIX, Buffer.from(keys.seedHex, 'hex')]), format: 'der', type: 'pkcs8',
    });
    const spki = createPublicKey(this.privateKey).export({ format: 'der', type: 'spki' });
    this.publicKey = `ed25519:${baseEncode(spki.subarray(-32))}`;
  }
  static generateKeys(): OracleKeysV2 {
    const { privateKey } = generateKeyPairSync('ed25519');
    const pkcs8 = privateKey.export({ format: 'der', type: 'pkcs8' });
    return { seedHex: pkcs8.subarray(-32).toString('hex') };
  }
  // For the owner's later deployment only. Tests keep throwaway keys in memory.
  static loadOrCreate(path: string): OralysOracleV2 {
    if (!existsSync(path)) {
      mkdirSync(dirname(path), { recursive: true });
      writeFileSync(path, JSON.stringify(OralysOracleV2.generateKeys()), { mode: 0o600, flag: 'wx' });
    }
    return new OralysOracleV2(JSON.parse(readFileSync(path, 'utf8')));
  }
  static signingMessage(contractId: string, requestId: string | number, excerptId: string,
    excerptHash: string, recordedAt: string | number, score: number): string {
    return [SIGNING_DOMAIN, contractId, String(requestId), excerptId, excerptHash, String(recordedAt), String(score)].join('|');
  }
  signExcerpt(contractId: string, requestId: string | number, excerptId: string,
    excerptHash: string, recordedAt: string | number, score: number): string {
    const message = OralysOracleV2.signingMessage(contractId, requestId, excerptId, excerptHash, recordedAt, score);
    return sign(null, Buffer.from(message, 'utf8'), this.privateKey).toString('hex');
  }
}
