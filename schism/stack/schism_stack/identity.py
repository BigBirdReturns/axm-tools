"""Operator-held Ed25519 identities and purpose-bound signed JSON envelopes.

Embedded public keys prove signature consistency. Recipient authorization and
independently learned key fingerprints remain separate decisions.
"""
from __future__ import annotations

import base64
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .common import Refusal, atomic_json, file_lock, now, private_root

IDENTITY_SCHEMA = "schism.identity/v1"
SIGNATURE_SCHEMA = "schism.signature/v1"
IDENTITY_FIELDS = {"schema", "name", "key_id", "public_key", "created_at"}
ENVELOPE_FIELDS = {"schema", "purpose", "key_id", "public_key", "payload", "signature"}


def canonical(value) -> bytes:
    """The stack's canonical form: sorted JSON, finite numbers, UTF-8 bytes."""
    def check(item, depth=0):
        if depth > 100:
            raise Refusal("Signed JSON exceeds the nesting limit")
        if item is None or isinstance(item, (str, bool, int)):
            return
        if isinstance(item, float):
            if not math.isfinite(item):
                raise Refusal("Signed JSON requires finite numbers")
            return
        if isinstance(item, list):
            for child in item:
                check(child, depth + 1)
            return
        if isinstance(item, dict) and all(isinstance(key, str) for key in item):
            for child in item.values():
                check(child, depth + 1)
            return
        raise Refusal("Signed JSON contains an unsupported value or object key")
    try:
        check(value)
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, Refusal):
            raise
        raise Refusal("Invalid canonical JSON: " + str(exc)) from exc


def key_id(public_raw: bytes) -> str:
    if not isinstance(public_raw, bytes) or len(public_raw) != 32:
        raise Refusal("Ed25519 public key must contain exactly 32 bytes")
    return hashlib.sha256(public_raw).hexdigest()


def _decode(value, size, label):
    try:
        if not isinstance(value, str) or len(value) > 256:
            raise ValueError("Invalid encoded length")
        raw = base64.b64decode(value, validate=True)
        if len(raw) != size or base64.b64encode(raw).decode("ascii") != value:
            raise ValueError("Noncanonical base64 or wrong byte length")
        return raw
    except (ValueError, TypeError) as exc:
        raise Refusal("Invalid " + label) from exc


def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise Refusal("Duplicate JSON field: " + key)
        out[key] = value
    return out


def _read_descriptor(path):
    try:
        if path.stat().st_size > 16384:
            raise Refusal("Identity descriptor is oversized")
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(Refusal("Invalid JSON number")))
    except (OSError, ValueError, UnicodeError) as exc:
        if isinstance(exc, Refusal):
            raise
        raise Refusal("Cannot read operator identity: " + str(exc)) from exc


def validate_descriptor(value):
    if not isinstance(value, dict) or set(value) != IDENTITY_FIELDS or value.get("schema") != IDENTITY_SCHEMA:
        raise Refusal("Unknown operator identity fields or schema")
    if not isinstance(value["name"], str) or not value["name"].strip() or len(value["name"]) > 200:
        raise Refusal("Operator identity needs a bounded display name")
    if not isinstance(value["created_at"], str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value["created_at"]):
        raise Refusal("Operator identity requires a UTC creation timestamp")
    try:
        datetime.fromisoformat(value["created_at"][:-1] + "+00:00")
    except ValueError as exc:
        raise Refusal("Invalid identity creation timestamp") from exc
    raw = _decode(value["public_key"], 32, "operator public key")
    if value["key_id"] != key_id(raw):
        raise Refusal("Operator fingerprint differs from its public key")
    canonical(value)
    return raw


def _regular(path):
    try:
        info = path.lstat()
    except OSError as exc:
        raise Refusal("Identity file is unavailable: " + str(exc)) from exc
    if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise Refusal("Identity files must be regular files, without reparse points")
    if info.st_nlink != 1:
        raise Refusal("Identity files cannot have additional hard links")
    return info


def _protect_windows(path):
    """Restrict files or directory trees to their owner using the Windows API.

    OI/CI directory entries inherit to files and subdirectories. Windows applies
    the changed inheritable DACL to existing unprotected descendants as well.
    """
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    descriptor = ctypes.c_void_p()
    convert = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    convert.restype = wintypes.BOOL
    get_dacl = advapi.GetSecurityDescriptorDacl
    get_dacl.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL), ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.BOOL)]
    get_dacl.restype = wintypes.BOOL
    apply = advapi.SetNamedSecurityInfoW
    apply.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                      ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    apply.restype = wintypes.DWORD
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    inheritance = "OICI" if Path(path).is_dir() else ""
    if not convert("D:P(A;" + inheritance + ";FA;;;OW)", 1, ctypes.byref(descriptor), None):
        raise Refusal("Windows could not construct the owner-only state ACL")
    try:
        present, defaulted, dacl = wintypes.BOOL(), wintypes.BOOL(), ctypes.c_void_p()
        if not get_dacl(descriptor, ctypes.byref(present), ctypes.byref(dacl), ctypes.byref(defaulted)) or not present.value:
            raise Refusal("Windows could not read the owner-only state ACL")
        result = apply(str(path), 1, 0x80000004, None, None, dacl, None)
        if result:
            raise Refusal("Windows could not restrict private-state access; error " + str(result))
    finally:
        kernel.LocalFree(descriptor)


def _private_directory(path):
    path = Path(os.path.abspath(Path(path).expanduser()))
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise Refusal("Private identity paths cannot traverse links or junctions")
    return private_root(path)


def ensure_identity(state: Path, name: str = "Local operator") -> dict:
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        raise Refusal("Operator name must contain 1 to 200 characters")
    root = _private_directory(state)
    marker = root / "schism-state.json"
    if not marker.exists():
        if any(root.iterdir()):
            raise Refusal("Identity creation requires empty or initialized SCHISM state")
        atomic_json(marker, {"schema": "schism.state/v1", "created_at": now()})
    else:
        _regular(marker)
        marker_value = _read_descriptor(marker)
        if not isinstance(marker_value, dict) or marker_value.get("schema") != "schism.state/v1":
            raise Refusal("Unsupported state marker")
    _protect_windows(root)
    locks = _private_directory(root / "locks")
    with file_lock(locks / "identity.lock"):
        directory = _private_directory(root / "identity")
        private, public = directory / "private.key", directory / "public.json"
        if private.exists() or public.exists() or private.is_symlink() or public.is_symlink():
            if not private.exists() or not public.exists():
                raise Refusal("Incomplete operator identity; restore it rather than creating a replacement key")
            info = _regular(private)
            _regular(public)
            if info.st_size != 32:
                raise Refusal("Invalid private-key length")
            if os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077:
                raise Refusal("Private signing key permissions must exclude group and other access")
            _protect_windows(private)
            descriptor = _read_descriptor(public)
            raw = validate_descriptor(descriptor)
            derived = Ed25519PrivateKey.from_private_bytes(private.read_bytes()).public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            if raw != derived:
                raise Refusal("Private key differs from the retained public identity")
            return descriptor
        signing = Ed25519PrivateKey.generate()
        raw_private = signing.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                           serialization.NoEncryption())
        raw_public = signing.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        descriptor = {"schema": IDENTITY_SCHEMA, "name": name.strip(), "key_id": key_id(raw_public),
                      "public_key": base64.b64encode(raw_public).decode("ascii"), "created_at": now()}
        fd = os.open(private, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw_private)
            handle.flush()
            os.fsync(handle.fileno())
        _protect_windows(private)
        atomic_json(public, descriptor)
        return descriptor


def sign(state: Path, payload: dict, purpose: str) -> dict:
    if not isinstance(payload, dict):
        raise Refusal("Signed payload must be a JSON object")
    if not isinstance(purpose, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._/-]{0,119}", purpose):
        raise Refusal("A bounded, explicit signature purpose is required")
    descriptor = ensure_identity(state)
    body = {"schema": SIGNATURE_SCHEMA, "purpose": purpose, "key_id": descriptor["key_id"],
            "public_key": descriptor["public_key"], "payload": payload}
    private = Path(os.path.abspath(Path(state).expanduser())) / "identity" / "private.key"
    _regular(private)
    signature = Ed25519PrivateKey.from_private_bytes(private.read_bytes()).sign(canonical(body))
    return {**body, "signature": base64.b64encode(signature).decode("ascii")}


def verify(envelope: dict, purpose: str | None = None, expected_key_id: str | None = None) -> dict:
    if not isinstance(envelope, dict) or set(envelope) != ENVELOPE_FIELDS or envelope.get("schema") != SIGNATURE_SCHEMA:
        raise Refusal("Unknown signature envelope fields or schema")
    if not isinstance(envelope["purpose"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9._/-]{0,119}", envelope["purpose"]):
        raise Refusal("Invalid signature purpose")
    if purpose is not None and envelope["purpose"] != purpose:
        raise Refusal("Signature has a different purpose")
    raw = _decode(envelope["public_key"], 32, "signature public key")
    if envelope["key_id"] != key_id(raw):
        raise Refusal("Signature fingerprint differs from its public key")
    if expected_key_id is not None and envelope["key_id"] != expected_key_id:
        raise Refusal("Signature is not from the expected identity")
    if not isinstance(envelope["payload"], dict):
        raise Refusal("Signed payload must be a JSON object")
    signature = _decode(envelope["signature"], 64, "Ed25519 signature")
    body = {key: value for key, value in envelope.items() if key != "signature"}
    try:
        Ed25519PublicKey.from_public_bytes(raw).verify(signature, canonical(body))
    except (InvalidSignature, ValueError) as exc:
        raise Refusal("Ed25519 signature verification failed") from exc
    return envelope["payload"]
