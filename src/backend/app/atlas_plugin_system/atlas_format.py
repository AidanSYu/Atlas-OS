"""
.atlas binary container format for the Atlas Framework plugin system.

Layout
------
MAGIC           8 bytes     b"ATLAS\\x00\\x01\\x00"
FLAGS           4 bytes     uint32-LE  (bit 0 = encrypted, bit 1 = has_assets)
MANIFEST_SIZE   4 bytes     uint32-LE
CODE_SIZE       4 bytes     uint32-LE
ASSETS_SIZE     4 bytes     uint32-LE
MANIFEST        variable    JSON (always cleartext so the orchestrator can inspect)
CODE            variable    compiled bytecode; AES-256-GCM encrypted when flag set
ASSETS          variable    zip bundle of data files; encrypted when flag set
SIGNATURE       32 bytes    HMAC-SHA256 over everything preceding it

Encryption uses AES-256-GCM.  The 256-bit key is derived from a user-
supplied passphrase via PBKDF2-HMAC-SHA256 (600 000 iterations).  A random
16-byte salt is prepended to the encrypted section, followed by a 12-byte
nonce and a 16-byte GCM auth tag, then the ciphertext:

    SALT (16) | NONCE (12) | TAG (16) | CIPHERTEXT (variable)

The manifest is *never* encrypted — it is always readable so the orchestrator
can discover tool name, description, and input schema without a key.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import marshal
import os
import struct
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ATLAS_MAGIC = b"ATLAS\x00\x01\x00"  # 8 bytes
HEADER_SIZE = len(ATLAS_MAGIC) + 4 + 4 + 4 + 4  # magic + flags + 3 sizes = 24
SIGNATURE_SIZE = 32  # HMAC-SHA256

FLAG_ENCRYPTED = 1 << 0
FLAG_HAS_ASSETS = 1 << 1

PBKDF2_ITERATIONS = 600_000
SALT_SIZE = 16
NONCE_SIZE = 12
GCM_TAG_SIZE = 16

# HMAC key used for tamper detection (not secret — prevents casual edits)
_HMAC_KEY = b"atlas-framework-integrity-v1"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AtlasPackage:
    """In-memory representation of a parsed .atlas file."""

    manifest: Dict[str, Any]
    code_bytes: bytes  # marshalled bytecode (decrypted)
    assets_bytes: bytes  # raw zip bundle (decrypted), may be empty
    flags: int = 0
    source_path: Optional[Path] = None

    @property
    def is_encrypted(self) -> bool:
        return bool(self.flags & FLAG_ENCRYPTED)

    @property
    def has_assets(self) -> bool:
        return bool(self.flags & FLAG_HAS_ASSETS)


# ---------------------------------------------------------------------------
# Encryption helpers (AES-256-GCM via cryptography library)
# ---------------------------------------------------------------------------

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit AES key from a passphrase using PBKDF2."""
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, PBKDF2_ITERATIONS)


def _encrypt_section(plaintext: bytes, passphrase: str) -> bytes:
    """Encrypt bytes with AES-256-GCM, returning SALT|NONCE|TAG|CIPHERTEXT."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = os.urandom(SALT_SIZE)
    key = _derive_key(passphrase, salt)
    nonce = os.urandom(NONCE_SIZE)
    aes = AESGCM(key)
    ciphertext = aes.encrypt(nonce, plaintext, None)
    # ciphertext already has the GCM tag appended by cryptography lib
    return salt + nonce + ciphertext


def _decrypt_section(blob: bytes, passphrase: str) -> bytes:
    """Decrypt a SALT|NONCE|TAG|CIPHERTEXT blob produced by _encrypt_section."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if len(blob) < SALT_SIZE + NONCE_SIZE + GCM_TAG_SIZE:
        raise ValueError("Encrypted section is too short to contain salt+nonce+tag")

    salt = blob[:SALT_SIZE]
    nonce = blob[SALT_SIZE : SALT_SIZE + NONCE_SIZE]
    ciphertext_with_tag = blob[SALT_SIZE + NONCE_SIZE :]

    key = _derive_key(passphrase, salt)
    aes = AESGCM(key)
    return aes.decrypt(nonce, ciphertext_with_tag, None)


# ---------------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------------

def _compute_signature(payload: bytes) -> bytes:
    """HMAC-SHA256 over the entire file payload (everything before the sig)."""
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
    """Compile source code and pack everything into the .atlas binary format.

    Parameters
    ----------
    manifest : dict
        Plugin manifest (must include at least ``name`` and ``description``).
    source_code : str
        Python source for the wrapper module.
    assets_bytes : bytes
        Optional zip bundle of data files to embed.
    passphrase : str or None
        If provided, encrypts the code (and assets) section with AES-256-GCM.

    Returns
    -------
    bytes
        The complete .atlas file contents ready to write to disk.
    """
    # Compile to bytecode — this is what gets embedded (not raw source)
    code_object = compile(source_code, f"<atlas:{manifest.get('name', 'unknown')}>", "exec")
    raw_code = marshal.dumps(code_object)

    # Determine flags
    flags = 0
    if passphrase:
        flags |= FLAG_ENCRYPTED
    if assets_bytes:
        flags |= FLAG_HAS_ASSETS

    # Encrypt if needed
    if passphrase:
        code_section = _encrypt_section(raw_code, passphrase)
        assets_section = _encrypt_section(assets_bytes, passphrase) if assets_bytes else b""
    else:
        code_section = raw_code
        assets_section = assets_bytes

    # Manifest is always cleartext JSON
    manifest_bytes = json.dumps(manifest, ensure_ascii=True, indent=2).encode("utf-8")

    # Assemble
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
    """Pack and write a .atlas file to disk."""
    data = pack_atlas(manifest, source_code, assets_bytes=assets_bytes, passphrase=passphrase)
    output_path = Path(output_path)
    output_path.write_bytes(data)
    logger.info("Wrote .atlas package: %s (%d bytes)", output_path, len(data))
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
    """Read and parse a .atlas binary file.

    Parameters
    ----------
    file_path : Path
        Path to the .atlas file.
    passphrase : str or None
        Required if the package is encrypted.
    verify_signature : bool
        Whether to check the HMAC signature (default True).
    manifest_only : bool
        If True, only parse the manifest and skip code/asset decryption.

    Returns
    -------
    AtlasPackage
    """
    raw = Path(file_path).read_bytes()

    if len(raw) < HEADER_SIZE + SIGNATURE_SIZE:
        raise ValueError(f"File too small to be a valid .atlas package: {file_path}")

    if raw[:len(ATLAS_MAGIC)] != ATLAS_MAGIC:
        raise ValueError(f"Invalid .atlas magic bytes in {file_path}")

    # Verify signature
    if verify_signature:
        stored_sig = raw[-SIGNATURE_SIZE:]
        payload = raw[:-SIGNATURE_SIZE]
        expected_sig = _compute_signature(payload)
        if not hmac.compare_digest(stored_sig, expected_sig):
            raise ValueError(f"Signature verification failed for {file_path} — file may be tampered")

    # Parse header
    offset = len(ATLAS_MAGIC)
    flags = struct.unpack_from("<I", raw, offset)[0]
    offset += 4
    manifest_size = struct.unpack_from("<I", raw, offset)[0]
    offset += 4
    code_size = struct.unpack_from("<I", raw, offset)[0]
    offset += 4
    assets_size = struct.unpack_from("<I", raw, offset)[0]
    offset += 4

    # Read manifest (always cleartext)
    manifest_bytes = raw[offset : offset + manifest_size]
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    offset += manifest_size

    if manifest_only:
        return AtlasPackage(
            manifest=manifest,
            code_bytes=b"",
            assets_bytes=b"",
            flags=flags,
            source_path=Path(file_path),
        )

    # Read code section
    code_blob = raw[offset : offset + code_size]
    offset += code_size

    # Read assets section
    assets_blob = raw[offset : offset + assets_size]

    # Decrypt if encrypted
    is_encrypted = bool(flags & FLAG_ENCRYPTED)
    if is_encrypted:
        if not passphrase:
            raise ValueError(
                f"Package {file_path} is encrypted but no passphrase was provided. "
                "Set ATLAS_PLUGIN_KEY environment variable or pass --key to atlas-sdk."
            )
        code_bytes = _decrypt_section(code_blob, passphrase)
        assets_bytes = _decrypt_section(assets_blob, passphrase) if assets_blob else b""
    else:
        code_bytes = code_blob
        assets_bytes = assets_blob

    return AtlasPackage(
        manifest=manifest,
        code_bytes=code_bytes,
        assets_bytes=assets_bytes,
        flags=flags,
        source_path=Path(file_path),
    )


# ---------------------------------------------------------------------------
# Loader — execute bytecode into a module
# ---------------------------------------------------------------------------

def load_atlas_module(package: AtlasPackage) -> types.ModuleType:
    """Unmarshal the bytecode from an AtlasPackage and exec it into a module.

    If the package contains an asset bundle, assets are extracted to a
    persistent cache directory and the path is injected into the module
    namespace as ``__atlas_assets__``.  Wrappers can reference embedded
    GGUF models, native libraries, ONNX files, etc. via this path::

        model_path = __atlas_assets__ / "model.gguf"

    Returns a module object with the wrapper's namespace (PLUGIN, invoke, etc.).
    """
    from app.atlas_plugin_system.atlas_runtime import extract_assets

    name = package.manifest.get("name", "unknown")
    module_name = f"atlas_plugin_{name}"

    code_object = marshal.loads(package.code_bytes)

    module = types.ModuleType(module_name)
    module.__file__ = f"<atlas:{name}>"
    module.__loader__ = None

    # Extract assets and inject path into module namespace before exec
    if package.has_assets and package.assets_bytes:
        assets_dir = extract_assets(name, package.assets_bytes)
    else:
        assets_dir = None
    module.__dict__["__atlas_assets__"] = assets_dir
    module.__dict__["__atlas_manifest__"] = package.manifest

    exec(code_object, module.__dict__)
    return module


# ---------------------------------------------------------------------------
# Convenience: inspect manifest without loading code
# ---------------------------------------------------------------------------

def inspect_atlas(file_path: Path) -> Dict[str, Any]:
    """Read only the manifest from a .atlas file (no decryption needed)."""
    pkg = read_atlas(file_path, verify_signature=False, manifest_only=True)
    return {
        "manifest": pkg.manifest,
        "encrypted": pkg.is_encrypted,
        "has_assets": pkg.has_assets,
        "file_size": Path(file_path).stat().st_size,
    }
