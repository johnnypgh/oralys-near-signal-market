// Seller side: the Oralys oracle. It holds an ed25519 signing key off chain and
// signs (contract, request id, signal id, keyed hash, quality score).
// Key material is generated locally and stored in a gitignored file. Test use only.
import { createHmac, createPrivateKey, createPublicKey, generateKeyPairSync, sign, randomBytes } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync, chmodSync } from "node:fs";
import { dirname } from "node:path";
import { baseEncode } from "near-api-js";

export const SIGNING_DOMAIN = "oralys-signal-v1";

// PKCS8 DER prefix for a raw 32 byte ed25519 seed.
const PKCS8_ED25519_PREFIX = Buffer.from("302e020100300506032b657004220420", "hex");

export interface OracleKeys {
  seedHex: string; // ed25519 private seed (32 bytes)
  hmacKeyHex: string; // key for the transcript keyed hash (32 bytes)
}

export class OralysOracle {
  private readonly privateKey;
  readonly publicKey: string; // "ed25519:<base58>" as NEAR expects
  private readonly hmacKey: Buffer;

  constructor(keys: OracleKeys) {
    const seed = Buffer.from(keys.seedHex, "hex");
    if (seed.length !== 32) throw new Error("oracle seed must be 32 bytes");
    this.privateKey = createPrivateKey({ key: Buffer.concat([PKCS8_ED25519_PREFIX, seed]), format: "der", type: "pkcs8" });
    const spki = createPublicKey(this.privateKey).export({ format: "der", type: "spki" }) as Buffer;
    const raw = spki.subarray(spki.length - 32);
    this.publicKey = `ed25519:${baseEncode(raw)}`;
    this.hmacKey = Buffer.from(keys.hmacKeyHex, "hex");
  }

  static generateKeys(): OracleKeys {
    const { privateKey } = generateKeyPairSync("ed25519");
    const pkcs8 = privateKey.export({ format: "der", type: "pkcs8" }) as Buffer;
    return { seedHex: pkcs8.subarray(pkcs8.length - 32).toString("hex"), hmacKeyHex: randomBytes(32).toString("hex") };
  }

  /** Loads keys from a gitignored file, creating them on first use. Never prints them. */
  static loadOrCreate(path: string): OralysOracle {
    if (!existsSync(path)) {
      mkdirSync(dirname(path), { recursive: true });
      writeFileSync(path, JSON.stringify(OralysOracle.generateKeys(), null, 2));
      chmodSync(path, 0o600);
    }
    return new OralysOracle(JSON.parse(readFileSync(path, "utf8")));
  }

  /** Keyed hash of the transcript text. Only this goes on chain, never the text. */
  keyedHash(transcript: string): string {
    return createHmac("sha256", this.hmacKey).update(transcript, "utf8").digest("hex");
  }

  static signingMessage(contractId: string, requestId: string | number, signalId: string, keyedHash: string, score: number): string {
    return [SIGNING_DOMAIN, contractId, String(requestId), signalId, keyedHash, String(score)].join("|");
  }

  signFulfillment(contractId: string, requestId: string | number, signalId: string, keyedHash: string, score: number): string {
    const msg = OralysOracle.signingMessage(contractId, requestId, signalId, keyedHash, score);
    return sign(null, Buffer.from(msg, "utf8"), this.privateKey).toString("hex");
  }
}
