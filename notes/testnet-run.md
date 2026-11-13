# Oralys Signal Market testnet demo run

SAMPLE DATA only. Testnet NEAR only, no real money.

- Started: 2026-11-12T23:14:44.197Z (UTC)
- market: market.oralys-signal.testnet
- buyer: buyer.oralys-signal.testnet
- seller: seller.oralys-signal.testnet
- signer_public_key: ed25519:6D2PVtfmgJybPk6PF8iKPHr33eQriJAHnR7YP7B6SSNr
- wasm_sha256_bs58: ACVxqCa67pvtCnBrvJzgFWndXbNQ8tF1zoVRgQSpKBFC

| # | Step | Result | Transaction |
| --- | --- | --- | --- |
| 1 | open_request #1 | ok | [6Jq6eoWrVYH6CBTLv1JNnaoDCUJ2PdebgT78osmSAQf3](https://testnet.nearblocks.io/txns/6Jq6eoWrVYH6CBTLv1JNnaoDCUJ2PdebgT78osmSAQf3) |
| 2 | fulfill #1 | ok | [8QhgXaHN8zX4W37NcqidHP4N7DMqG8TB3umU7L37Mn28](https://testnet.nearblocks.io/txns/8QhgXaHN8zX4W37NcqidHP4N7DMqG8TB3umU7L37Mn28) |
| 3 | open_request #2 | ok | [2ethFqpbdEBcFTR4bdFWSsee9Cb1zDdK9zNpbAnmbeeb](https://testnet.nearblocks.io/txns/2ethFqpbdEBcFTR4bdFWSsee9Cb1zDdK9zNpbAnmbeeb) |
| 4 | fulfill #2 | ok | [5tCosw1Lrzk9GJ3EX2pXpwaijHX4CeVHxgwAjGawXG5z](https://testnet.nearblocks.io/txns/5tCosw1Lrzk9GJ3EX2pXpwaijHX4CeVHxgwAjGawXG5z) |
| 5 | open_request #3 | ok | [8GM64izRcd9jmGU95v3Juzsnsv6r9Zj4gTmSxvmP5QTj](https://testnet.nearblocks.io/txns/8GM64izRcd9jmGU95v3Juzsnsv6r9Zj4gTmSxvmP5QTj) |
| 6 | fulfill #3 | ok | [2LSxyngZUHGQYvKQUBa8hgawiZaUB9SBr5KofC4tWB6D](https://testnet.nearblocks.io/txns/2LSxyngZUHGQYvKQUBa8hgawiZaUB9SBr5KofC4tWB6D) |
| 7 | open_request #4 | ok | [CwZ3gdjBFVpAs4GnKTJk8oUTHRMKhAVkc6SCqAaEp6gE](https://testnet.nearblocks.io/txns/CwZ3gdjBFVpAs4GnKTJk8oUTHRMKhAVkc6SCqAaEp6gE) |
| 8 | fulfill with forged signature | rejected: invalid signature | [92yzx3mbKFArpVWcfWHW7hv1q8oGqQkKQEofr6kL1Fm9](https://testnet.nearblocks.io/txns/92yzx3mbKFArpVWcfWHW7hv1q8oGqQkKQEofr6kL1Fm9) |
| 9 | fulfill below minimum | rejected: quality score below buyer minimum | [GB16nbqJgCTkGHUJ9F3ZA4Qb74fxFJFVrwoJXJAnPTmu](https://testnet.nearblocks.io/txns/GB16nbqJgCTkGHUJ9F3ZA4Qb74fxFJFVrwoJXJAnPTmu) |
| 10 | refund after deadline | ok | [4XsmTRb27cMrAq6tDfT2j6buBUtTyRrunSnPqqnGq773](https://testnet.nearblocks.io/txns/4XsmTRb27cMrAq6tDfT2j6buBUtTyRrunSnPqqnGq773) |
