# -*- coding: utf-8 -*-
"""
Kingbot encryption (v196): AES-256-GCM for everything the bot publishes in the public kingbot-syn repo.

Key:  PBKDF2-HMAC-SHA256(passphrase, salt="kingbot-syn:v1", 200000 iterations) -> 32 bytes.
      The passphrase is ONLY in C:\\RisBot\\local_config.json ("KB_PASSPHRASE") on the server and in the
      browser of whoever opens the dashboard. It never goes to GitHub.
kid:  first 16 hex chars of SHA-256(key) - lets the dashboard say "wrong passphrase" instead of garbage.

JSON envelope (status.json, control.json):
    {"enc": "kb1", "kid": "...", "iv": b64(12 bytes), "ct": b64(ciphertext + 16-byte tag), ...public fields}
Binary envelope (screen.jpg):  b"KBE1" + kid(8 bytes) + iv(12) + ciphertext + tag(16)

Uses the `cryptography` package when it is installed; otherwise a small pure-Python AES-GCM
(slower, but the files are small). Both produce identical output and match the browser (WebCrypto).
"""
import os, json, base64, hashlib, struct

SALT = b"kingbot-syn:v1"
ITER = 200_000
MAGIC = b"KBE1"
_KEYS = {}


def derive(passphrase):
    p = str(passphrase or "")
    if p not in _KEYS:
        _KEYS[p] = hashlib.pbkdf2_hmac("sha256", p.encode("utf-8"), SALT, ITER, 32)
    return _KEYS[p]


def kid(key):
    return hashlib.sha256(key).hexdigest()[:16]


# ---------------------------------------------------------------- AES-GCM backends
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM

    def _seal(key, iv, data):
        return _AESGCM(key).encrypt(iv, data, None)

    def _open(key, iv, data):
        return _AESGCM(key).decrypt(iv, data, None)

    BACKEND = "cryptography"
except Exception:                                    # pure Python fallback
    BACKEND = "python"
    _SBOX = [0] * 256
    _p = _q = 1
    while True:                                      # build the AES S-box
        _p = _p ^ ((_p << 1) & 0xFF) ^ (0x1B if _p & 0x80 else 0)
        _q ^= _q << 1; _q ^= _q << 2; _q ^= _q << 4; _q &= 0xFF
        if _q & 0x80: _q ^= 0x09
        _x = _q ^ ((_q << 1) | (_q >> 7)) ^ ((_q << 2) | (_q >> 6)) ^ ((_q << 3) | (_q >> 5)) ^ ((_q << 4) | (_q >> 4))
        _SBOX[_p] = (_x ^ 0x63) & 0xFF
        if _p == 1: break
    _SBOX[0] = 0x63

    def _xt(a):
        return ((a << 1) ^ 0x1B) & 0xFF if a & 0x80 else a << 1

    # T-tables for fast rounds
    _T0 = []
    for _s in _SBOX:
        _s2 = _xt(_s); _s3 = _s2 ^ _s
        _T0.append((_s2 << 24) | (_s << 16) | (_s << 8) | _s3)
    _T1 = [((t >> 8) | (t << 24)) & 0xFFFFFFFF for t in _T0]
    _T2 = [((t >> 16) | (t << 16)) & 0xFFFFFFFF for t in _T0]
    _T3 = [((t >> 24) | (t << 8)) & 0xFFFFFFFF for t in _T0]

    def _expand(key):
        nk, nr = 8, 14
        w = list(struct.unpack(">8I", key))
        rcon = 1
        for i in range(nk, 4 * (nr + 1)):
            t = w[i - 1]
            if i % nk == 0:
                t = ((t << 8) | (t >> 24)) & 0xFFFFFFFF
                t = (_SBOX[t >> 24] << 24) | (_SBOX[(t >> 16) & 255] << 16) | (_SBOX[(t >> 8) & 255] << 8) | _SBOX[t & 255]
                t ^= rcon << 24
                rcon = _xt(rcon)
            elif i % nk == 4:
                t = (_SBOX[t >> 24] << 24) | (_SBOX[(t >> 16) & 255] << 16) | (_SBOX[(t >> 8) & 255] << 8) | _SBOX[t & 255]
            w.append(w[i - nk] ^ t)
        return w

    def _enc_block(w, blk):
        s0, s1, s2, s3 = struct.unpack(">4I", blk)
        s0 ^= w[0]; s1 ^= w[1]; s2 ^= w[2]; s3 ^= w[3]
        k = 4
        for _ in range(13):
            t0 = _T0[s0 >> 24] ^ _T1[(s1 >> 16) & 255] ^ _T2[(s2 >> 8) & 255] ^ _T3[s3 & 255] ^ w[k]
            t1 = _T0[s1 >> 24] ^ _T1[(s2 >> 16) & 255] ^ _T2[(s3 >> 8) & 255] ^ _T3[s0 & 255] ^ w[k + 1]
            t2 = _T0[s2 >> 24] ^ _T1[(s3 >> 16) & 255] ^ _T2[(s0 >> 8) & 255] ^ _T3[s1 & 255] ^ w[k + 2]
            t3 = _T0[s3 >> 24] ^ _T1[(s0 >> 16) & 255] ^ _T2[(s1 >> 8) & 255] ^ _T3[s2 & 255] ^ w[k + 3]
            s0, s1, s2, s3 = t0, t1, t2, t3
            k += 4
        S = _SBOX
        o0 = (S[s0 >> 24] << 24 | S[(s1 >> 16) & 255] << 16 | S[(s2 >> 8) & 255] << 8 | S[s3 & 255]) ^ w[k]
        o1 = (S[s1 >> 24] << 24 | S[(s2 >> 16) & 255] << 16 | S[(s3 >> 8) & 255] << 8 | S[s0 & 255]) ^ w[k + 1]
        o2 = (S[s2 >> 24] << 24 | S[(s3 >> 16) & 255] << 16 | S[(s0 >> 8) & 255] << 8 | S[s1 & 255]) ^ w[k + 2]
        o3 = (S[s3 >> 24] << 24 | S[(s0 >> 16) & 255] << 16 | S[(s1 >> 8) & 255] << 8 | S[s2 & 255]) ^ w[k + 3]
        return struct.pack(">4I", o0, o1, o2, o3)

    _R = 0xE1 << 120

    def _gmul_table(h):
        return h, None

    def _ghash_mul(x, h, _unused):
        """GF(2^128) multiply (GCM bit order), plain shift-and-add."""
        z, v = 0, h
        for i in range(127, -1, -1):
            if (x >> i) & 1:
                z ^= v
            v = (v >> 1) ^ _R if v & 1 else v >> 1
        return z

    def _ghash(tab, red, aad, ct):
        y = 0
        def blocks(b):
            for i in range(0, len(b), 16):
                yield int.from_bytes(b[i:i + 16].ljust(16, b"\0"), "big")
        for blk in blocks(aad):
            y = _ghash_mul(y ^ blk, tab, red)
        for blk in blocks(ct):
            y = _ghash_mul(y ^ blk, tab, red)
        y = _ghash_mul(y ^ ((len(aad) * 8) << 64 | (len(ct) * 8)), tab, red)
        return y

    def _ctr(w, j0, data):
        out = bytearray(len(data))
        ctr = int.from_bytes(j0, "big")
        for i in range(0, len(data), 16):
            ctr = (ctr & ~0xFFFFFFFF) | ((ctr + 1) & 0xFFFFFFFF)
            ks = _enc_block(w, ctr.to_bytes(16, "big"))
            chunk = data[i:i + 16]
            out[i:i + len(chunk)] = bytes(a ^ b for a, b in zip(chunk, ks))
        return bytes(out)

    def _prep(key, iv):
        w = _expand(key)
        h = int.from_bytes(_enc_block(w, b"\0" * 16), "big")
        j0 = iv + b"\0\0\0\1"
        return w, _gmul_table(h), j0

    def _seal(key, iv, data):
        w, (tab, red), j0 = _prep(key, iv)
        ct = _ctr(w, j0, data)
        s = _ghash(tab, red, b"", ct)
        tag = (s ^ int.from_bytes(_enc_block(w, j0), "big")).to_bytes(16, "big")
        return ct + tag

    def _open(key, iv, data):
        w, (tab, red), j0 = _prep(key, iv)
        ct, tag = data[:-16], data[-16:]
        s = _ghash(tab, red, b"", ct)
        if (s ^ int.from_bytes(_enc_block(w, j0), "big")).to_bytes(16, "big") != tag:
            raise ValueError("wrong key or damaged data")
        return _ctr(w, j0, ct)


# ---------------------------------------------------------------- public API
def seal_bytes(key, data):
    iv = os.urandom(12)
    return MAGIC + bytes.fromhex(kid(key)) + iv + _seal(key, iv, data)


def open_bytes(key, blob):
    if blob[:4] != MAGIC:
        return blob                                   # not encrypted
    if blob[4:12] != bytes.fromhex(kid(key)):
        raise ValueError("encrypted with another passphrase")
    return _open(key, blob[12:24], blob[24:])


def seal_json(key, obj, public=()):
    """Everything goes inside; the keys named in `public` are also kept readable outside."""
    iv = os.urandom(12)
    ct = _seal(key, iv, json.dumps(obj, ensure_ascii=False).encode("utf-8"))
    env = {k: obj[k] for k in public if k in obj}
    env.update(enc="kb1", kid=kid(key), iv=base64.b64encode(iv).decode(), ct=base64.b64encode(ct).decode())
    return env


def is_sealed(obj):
    return isinstance(obj, dict) and obj.get("enc") == "kb1"


def open_json(key, env):
    if not is_sealed(env):
        return env
    if env.get("kid") != kid(key):
        raise ValueError("encrypted with another passphrase")
    return json.loads(_open(key, base64.b64decode(env["iv"]), base64.b64decode(env["ct"])).decode("utf-8"))
