from __future__ import annotations

import hashlib
from modules.logger import log_action

_CHUNK = 65536  # 64 КБ — не грузим весь файл в память


def compute_hashes(filepath: str) -> dict[str, str]:
    """Вычисляет MD5 и SHA256 хэши файла блочным чтением.

    Работает корректно с файлами любого размера — данные читаются
    по 64 КБ, без загрузки целого файла в оперативную память.
    Хэши используются как криптографические доказательства целостности.
    """
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