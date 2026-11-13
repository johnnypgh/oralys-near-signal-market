# Attestation report store

`_tools/attest.py` writes raw attestation reports here only when they are small
enough to keep in git. Larger reports are stored as a SHA-256 in
notes/near-ai-attestation.json instead. This folder starts empty on purpose.
