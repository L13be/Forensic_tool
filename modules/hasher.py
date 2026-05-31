from __future__ import annotations

import hashlib
from modules.logger import log_action

_CHUNK = 65536


def compute_hashes(filepath: str) -> dict[str, str]:
    md5 = hashlib.md5()
    sha = hashlib.sha256()

    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            md5.update(chunk)
            sha.update(chunk)

    hashes = {
        "MD5":    md5.hexdigest(),
        "SHA256": sha.hexdigest(),
    }
    log_action(f"Вычислены хэши файла: {filepath} | MD5: {hashes['MD5']}")
    return hashes