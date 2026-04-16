"""
.atlas binary container format — standalone version for the SDK.

This is the same format used by the Atlas Framework runtime. The SDK ships
this module so researchers can build .atlas packages without installing the
full backend.

Layout
------
MAGIC           8 bytes     b"ATLAS\\x00\\x01\\x00"
FLAGS           4 bytes     uint32-LE  (bit 0 = encrypted, bit 1 = has_assets)
MANIFEST_SIZE   4 bytes     uint32-LE
CODE_SIZE       4 bytes     uint32-LE
ASSETS_SIZE     4 bytes     uint32-LE
MANIFEST        variable    JSON (always cleartext)
CODE            variable    compiled bytecode; AES-256-GCM encrypted when flag set
ASSETS          variable    zip bundle of data files; encrypted when flag set
SIGNATURE       32 bytes    HMAC-SHA256 over everything preceding it
"""

from __future__ import annotations

import hashlib
import hmac
import json
import marshal
import os
import struct
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ATLAS_MAGIC = b"ATLAS\x00\x01\x00"
HEADER_SIZE = len(ATLAS_MAGIC) + 4 + 4 + 4 + 4
SIGNATURE_SIZE = 32

FLAG_ENCRYPTED = 1 << 0
FLAG_HAS_ASSETS = 1 << 1

PBKDF2_ITERATIONS = 600_000
SALT_SIZE = 16
NONCE_SIZE = 12
GCM_TAG_SIZE = 16

_HMAC_KEY = b"atlas-framework-integrity-v1"


@dataclass
class AtlasPackage:
    """In-memory representation of a parsed .atlas file."""

    manifest: Dict[str, Any]
    code_bytes: bytes
    assets_bytes: bytes
    flags: int = 0
    source_path: Optional[Path] = None

    @property
    def is_encrypted(self) -> bool:
        return bool(self.flags & FLAG_ENCRYPTED)

    @property
    def has_assets(self) -> bool:
        return bool(self.flags & FLAG_HAS_ASSETS)


# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, PBKDF2_ITERATIONS)


def _encrypt_section(plaintext: bytes, passphrase: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = os.urandom(SALT_SIZE)
    key = _derive_key(passphrase, salt)
    nonce = os.urandom(NONCE_SIZE)
    aes = AESGCM(key)
    ciphertext = aes.encrypt(nonce, plaintext, None)
    return salt + nonce + ciphertext


def _decrypt_section(blob: bytes, passphrase: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if len(blob) < SALT_SIZE + NONCE_SIZE + GCM_TAG_SIZE:
        raise ValueError("Encrypted section is too short")
    salt = blob[:SALT_SIZE]
    nonce = blob[SALT_SIZE : SALT_SIZE + NONCE_SIZE]
    ciphertext_with_tag = blob[SALT_SIZE + NONCE_SIZE :]
    key = _derive_key(passphrase, salt)
    aes = AESGCM(key)
    return aes.decrypt(nonce, ciphertext_with_tag, None)


def _compute_signature(payload: bytes) -> bytes:
    return hmac.new(_HMAC_KEY, payload, hashlib.sha256).digest()


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def pack_atlas(
    manifest: Dict[str, Any],
    source_code: str,
    *,
    assets_bytes: bytes = b"",
    passphrase: Optional[str] = None,
) -> bytes:
    code_object = compile(source_code, f"<atlas:{manifest.get('name', 'unknown')}>", "exec")
    raw_code = marshal.dumps(code_object)

    flags = 0
    if passphrase:
        flags |= FLAG_ENCRYPTED
    if assets_bytes:
        flags |= FLAG_HAS_ASSETS

    if passphrase:
        code_section = _encrypt_section(raw_code, passphrase)
        assets_section = _encrypt_section(assets_bytes, passphrase) if assets_bytes else b""
    else:
        code_section = raw_code
        assets_section = assets_bytes

    manifest_bytes = json.dumps(manifest, ensure_ascii=True, indent=2).encode("utf-8")

    header = (
        ATLAS_MAGIC
        + struct.pack("<I", flags)
        + struct.pack("<I", len(manifest_bytes))
        + struct.pack("<I", len(code_section))
        + struct.pack("<I", len(assets_section))
    )

    payload = header + manifest_bytes + code_section + assets_section
    signature = _compute_signature(payload)
    return payload + signature


def write_atlas(
    output_path: Path,
    manifest: Dict[str, Any],
    source_code: str,
    *,
    assets_bytes: bytes = b"",
    passphrase: Optional[str] = None,
) -> Path:
    data = pack_atlas(manifest, source_code, assets_bytes=assets_bytes, passphrase=passphrase)
    output_path = Path(output_path)
    output_path.write_bytes(data)
    return output_path


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

def read_atlas(
    file_path: Path,
    *,
    passphrase: Optional[str] = None,
    verify_signature: bool = True,
    manifest_only: bool = False,
) -> AtlasPackage:
    raw = Path(file_path).read_bytes()

    if len(raw) < HEADER_SIZE + SIGNATURE_SIZE:
        raise ValueError(f"File too small to be a valid .atlas package: {file_path}")
    if raw[:len(ATLAS_MAGIC)] != ATLAS_MAGIC:
        raise ValueError(f"Invalid .atlas magic bytes in {file_path}")

    if verify_signature:
        stored_sig = raw[-SIGNATURE_SIZE:]
        payload = raw[:-SIGNATURE_SIZE]
        expected_sig = _compute_signature(payload)
        if not hmac.compare_digest(stored_sig, expected_sig):
            raise ValueError(f"Signature verification failed for {file_path}")

    offset = len(ATLAS_MAGIC)
    flags = struct.unpack_from("<I", raw, offset)[0]; offset += 4
    manifest_size = struct.unpack_from("<I", raw, offset)[0]; offset += 4
    code_size = struct.unpack_from("<I", raw, offset)[0]; offset += 4
    assets_size = struct.unpack_from("<I", raw, offset)[0]; offset += 4

    manifest = json.loads(raw[offset : offset + manifest_size].decode("utf-8"))
    offset += manifest_size

    if manifest_only:
        return AtlasPackage(manifest=manifest, code_bytes=b"", assets_bytes=b"",
                            flags=flags, source_path=Path(file_path))

    code_blob = raw[offset : offset + code_size]; offset += code_size
    assets_blob = raw[offset : offset + assets_size]

    if flags & FLAG_ENCRYPTED:
        if not passphrase:
            raise ValueError(f"Package {file_path} is encrypted — passphrase required")
        code_bytes = _decrypt_section(code_blob, passphrase)
        assets_bytes = _decrypt_section(assets_blob, passphrase) if assets_blob else b""
    else:
        code_bytes = code_blob
        assets_bytes = assets_blob

    return AtlasPackage(manifest=manifest, code_bytes=code_bytes, assets_bytes=assets_bytes,
                        flags=flags, source_path=Path(file_path))


def inspect_atlas(file_path: Path) -> Dict[str, Any]:
    pkg = read_atlas(file_path, verify_signature=False, manifest_only=True)
    return {
        "manifest": pkg.manifest,
        "encrypted": pkg.is_encrypted,
        "has_assets": pkg.has_assets,
        "file_size": Path(file_path).stat().st_size,
    }
