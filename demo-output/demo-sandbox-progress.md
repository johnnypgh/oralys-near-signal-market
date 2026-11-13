# Oralys Signal Market sandbox demo run

SAMPLE DATA only. Testnet NEAR only, no real money.

- Started: 2026-11-12T23:14:01.932Z (UTC)
- market: market.sandbox
- buyer: buyer.sandbox
- seller: seller.sandbox
- signer_public_key: ed25519:CkLUP92GtRWaJgPwnGLRoRC1bZ1maFt2yFyMrdYkpbd5
- wasm_sha256_bs58: ACVxqCa67pvtCnBrvJzgFWndXbNQ8tF1zoVRgQSpKBFC

| # | Step | Result | Transaction |
| --- | --- | --- | --- |
| 1 | create market.sandbox | ok | 4adQHXDSMxR5LpeGKm77Ws2pHuXriQFrTVyUYs9tS2nP |
| 2 | create buyer.sandbox | ok | 6oNahpLQh5RWGsuUjuW6Ub89vVJVib22rv1bkrVHkjUi |
| 3 | create seller.sandbox | ok | B4qWYQ8EvMtjK7JG2GKhSB95KE2xN6hb1ED8KD4qJ1b1 |
| 4 | deploy contract to market.sandbox | ok | 4Q9KRdeu8YYJ55atHHQSVxX9KaLKmqQ2dubwPvE26ZMR |
| 5 | init market | ok | C81qNrBqGR828EuUdx3CUXUU5ttppamrxbnQ38K475JZ |
| 6 | open_request #0 | ok | DxKPQZmu3MUqp6SZEn5Dwn4YWMbxBgREDEPWYSiYS4UX |
| 7 | fulfill #0 | ok | FtfAJHzqcprtKrB9DfViamuzx2QMtaSBviWbVF3A1tGr |
| 8 | open_request #1 | ok | FdkFjfh7ebrRofKaxbiVkNj8DCCYymFpsUphi2TRVqWe |
| 9 | fulfill #1 | ok | As8buUjYLDHL3egZNDTymL8syZKGciz15NHDB1EUjPQq |
| 10 | open_request #2 | ok | BLx2XSfu58UXH81VZZt2kagUAwbuFbUkYJQADkbTJ5Uu |
| 11 | fulfill #2 | ok | BS7kJSCp3iJHhQETXFozfG2uBA2MigJyx1shZVHfS9jS |
| 12 | open_request #3 | ok | BvmazYn3ZjzGjYYaxRRxViQBWVG1Fv8H3eUHah5HKQif |
| 13 | fulfill with forged signature | rejected: invalid signature | 7ztHzSCY9m2kznLxa4d2rTXbdaNYdjNMMv8jNjxqPufs |
| 14 | fulfill below minimum | rejected: quality score below buyer minimum | 56bVA2kYFXGQ4RCRokQ7iH1FcBXcDbJgw34L4k3y3hfw |
| 15 | refund after deadline | ok | 7RiJQ3HDxubqVgiJWdZAx7xbypMrV17YzSH7AC3CsbmG |
