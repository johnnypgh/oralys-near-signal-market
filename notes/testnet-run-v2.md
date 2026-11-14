# v2 testnet run (keyword requests)

Fri Nov 13, 2026, 12:19 AM ET. Testnet only. SAMPLE DATA only. Run on the box with `scripts/demo-v2.ts --network testnet`.

- Contract: `market2.oralys-signal.testnet` (https://testnet.nearblocks.io/address/market2.oralys-signal.testnet), code hash `GkDfZJkTx3EqgVpfUWLYYBadvenGi3Fx6biYJetfsxzQ`
- Owner `oralys-signal.testnet`, seller `seller.oralys-signal.testnet`, buyer `buyer.oralys-signal.testnet`, oracle signer `ed25519:9vZoLXg1rh1XH3CtrhL4RD8ZS5dpavb2nN6TwY9NTf7z`
- Request: `NVIDIA OR (Clarity AND Act)`, window 3600 s (default), 0.01 NEAR per excerpt, 0.05 NEAR deposit, min quality 70
- Read back after the run: request 0 Exhausted, 5 paid, 0.05 NEAR spent. Request 1 Refunded, 1 paid, 0.04 NEAR returned to the buyer.

| Step | Result | Tx |
| --- | --- | --- |
| create market2.oralys-signal.testnet, funded 2.3 NEAR from oralys-signal.testnet | ok | [7umU63b9qN](https://testnet.nearblocks.io/txns/7umU63b9qN4RR9hu1mBqj6SmEe3AfGCGqwyZcrKfHX6X) |
| deploy contract-v2 wasm and init new(owner, seller, signer) | ok | [ESvfnuxWY1](https://testnet.nearblocks.io/txns/ESvfnuxWY1ytpJ69WQpW1eHRt55eRcLsRVZPojXroZHz) |
| Open request with 600 second deadline | ok | [BvYm3SQQ7z](https://testnet.nearblocks.io/txns/BvYm3SQQ7z7t9qQn1jMV2u84FXSCTGePrKp2RwdFYZ3n) |
| Forged signature | REJECTED: invalid signature | [DTdGpbrvf3](https://testnet.nearblocks.io/txns/DTdGpbrvf3EZT4LoSuaSsG22emrhUwqMTZx8EsQK3hiz) |
| Out of window | REJECTED: recorded_at is outside the request window | [AmkxihxGkB](https://testnet.nearblocks.io/txns/AmkxihxGkBq73GXgx6VTRAg23KCs5qNr23fsadg4FYhC) |
| Low quality | REJECTED: quality score below buyer minimum | [J4z6zvoeJp](https://testnet.nearblocks.io/txns/J4z6zvoeJpZrKzoqBaa9D9TAasJw1xKRLiMVVoKeoetz) |
| Pay sd-r1-02-s2 | ok | [9jTJ1gokyG](https://testnet.nearblocks.io/txns/9jTJ1gokyGXEDn5Zgzi9RgjzEdVsc777tjKUQo25Vpbr) |
| Double pay | REJECTED: excerpt already paid for this request | [HRnpHwtwpm](https://testnet.nearblocks.io/txns/HRnpHwtwpmneRV8cvGiEq9iVUsNT3f3XQz69iZpiMMtm) |
| Pay sd-r2-01-s2 | ok | [96HrNvRgJg](https://testnet.nearblocks.io/txns/96HrNvRgJgNWDduhrx5YbWW2nCP32MDTBSifz38igcev) |
| Pay sd-r3-02-s2 | ok | [6w56ePCpRS](https://testnet.nearblocks.io/txns/6w56ePCpRSq3HzyjvLfUoMoGkuygFp68Vp2zDkmTx5CM) |
| Pay sd-r3-02-s5 | ok | [Hpd3gJyjcu](https://testnet.nearblocks.io/txns/Hpd3gJyjcutjkatFQavyhCfn3pCAK5KXEvy9DVQvkU76) |
| Pay sd-r4-01-s1 | ok | [289gEUdBLs](https://testnet.nearblocks.io/txns/289gEUdBLsDko6mdapwJukEC28equ2tMnZ8zqQcikvT4) |
| Open request with 20 second deadline | ok | [9Zk1iX78QM](https://testnet.nearblocks.io/txns/9Zk1iX78QMsHkao7RUeJSXRPruM8BEHbYNryj5iypic7) |
| Pay one excerpt on short request | ok | [HskNotrmzz](https://testnet.nearblocks.io/txns/HskNotrmzzdFzzxermuEmocaZQdMJYQVW7P2DRaZgHaL) |
| Refund after deadline | ok | [CEs5omy2JX](https://testnet.nearblocks.io/txns/CEs5omy2JXD7ysXp8ocTQ266BvUusc9c22WLSYm6dWFo) |
