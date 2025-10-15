#!/usr/bin/env python3
"""Generate random secrets for sensitive keys in a .env file.

Usage examples:
  python generate_env_secrets.py --dry-run
  python generate_env_secrets.py --output .env.generated
  python generate_env_secrets.py --in-place

The script detects common keys (POSTGRES_PASSWORD, JWT_SECRET, ANON_KEY, SERVICE_ROLE_KEY,
SECRET_KEY_BASE, VAULT_ENC_KEY, PG_META_CRYPTO_KEY, DASHBOARD_PASSWORD, LOGFLARE_*_ACCESS_TOKEN,
SMTP_PASS) and replaces their values with generated secure values.
"""
from __future__ import annotations

import argparse
import base64
import os
import secrets
import string
import sys
import uuid
from typing import Callable, Dict, List, Tuple


def generate_password(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits + "-_" + "!@#$%^&*()"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_base64(length_bytes: int = 32) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(length_bytes)).rstrip(b"=").decode()


def generate_uuid() -> str:
    return str(uuid.uuid4())


def generate_jwt_like() -> str:
    # Create a three-part JWT-like string (header.payload.signature) with base64 urlsafe parts
    def part(nbytes):
        return base64.urlsafe_b64encode(secrets.token_bytes(nbytes)).rstrip(b"=").decode()
    return f"{part(8)}.{part(20)}.{part(32)}"


DEFAULT_KEY_GENERATORS: List[Tuple[str, Callable[[], str]]] = [
    ("POSTGRES_PASSWORD", lambda: generate_password(40)),
    ("JWT_SECRET", lambda: generate_base64(32)),
    ("ANON_KEY", generate_jwt_like),
    ("SERVICE_ROLE_KEY", generate_jwt_like),
    ("DASHBOARD_PASSWORD", lambda: generate_password(20)),
    ("SECRET_KEY_BASE", lambda: generate_base64(48)),
    ("VAULT_ENC_KEY", lambda: generate_base64(24)),
    ("PG_META_CRYPTO_KEY", lambda: generate_base64(24)),
    ("LOGFLARE_PUBLIC_ACCESS_TOKEN", lambda: generate_base64(24)),
    ("LOGFLARE_PRIVATE_ACCESS_TOKEN", lambda: generate_base64(36)),
    ("SMTP_PASS", lambda: generate_password(24)),
    ("OPENAI_API_KEY", lambda: f"sk-{generate_base64(24)}"),
]


def detect_sensitive_key(key: str) -> bool:
    key = key.upper()
    sensitive_terms = [
        'SECRET', 'KEY', 'TOKEN', 'PASSWORD', 'PASS', 'ANON', 'SERVICE', 'ENC', 'PRIVATE'
    ]
    # Heuristic: if any sensitive term appears in the key name, consider it sensitive
    return any(term in key for term in sensitive_terms)


def load_env(path: str) -> List[str]:
    with open(path, 'r', encoding='utf-8') as f:
        return f.readlines()


def write_env(lines: List[str], path: str) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def parse_line(line: str) -> Tuple[str, str, str]:
    """Return (prefix, key, rest) where prefix is leading whitespace/comment, key is KEY=, rest is value+newline

    If the line is not a key=value line, key will be empty and rest==line.
    """
    stripped = line.lstrip()
    if not stripped or stripped.startswith('#') or '=' not in stripped:
        return (line[: len(line) - len(stripped)], '', stripped)
    # split only on the first = to preserve = in values
    left, right = stripped.split('=', 1)
    key = left.strip()
    return (line[: len(line) - len(stripped)], key, right)


def build_replacement_map(lines: List[str], custom_map: Dict[str, Callable[[], str]]) -> Dict[int, str]:
    replacements: Dict[int, str] = {}
    for idx, line in enumerate(lines):
        prefix, key, rest = parse_line(line)
        if not key:
            continue
        upper = key.upper()
        # exact match in provided map first
        if upper in (k.upper() for k in custom_map.keys()):
            # find the original key (case sensitive) to preserve casing
            for orig_k, gen in custom_map.items():
                if orig_k.upper() == upper:
                    val = gen()
                    replacements[idx] = f"{prefix}{orig_k}={val if val is not None else ''}\n"
                    break
            continue
        # default generators
        for k, gen in DEFAULT_KEY_GENERATORS:
            if upper == k:
                val = gen()
                replacements[idx] = f"{prefix}{k}={val}\n"
                break
        else:
            # heuristic detection
            if detect_sensitive_key(upper):
                # preserve key name and replace with a generated base64 string
                replacements[idx] = f"{prefix}{key}={generate_base64(24)}\n"
    return replacements


def apply_replacements(lines: List[str], replacements: Dict[int, str]) -> List[str]:
    new_lines = list(lines)
    for idx, new in replacements.items():
        new_lines[idx] = new
    return new_lines


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate random secrets for .env")
    parser.add_argument('--env', '-e', default=os.path.join('..', 'docker', '.env'), help='Path to source .env file')
    parser.add_argument('--output', '-o', help='Write updated .env to this file')
    parser.add_argument('--in-place', action='store_true', help='Overwrite the source .env file')
    parser.add_argument('--dry-run', action='store_true', help='Print replacements instead of writing')
    parser.add_argument('--seed', type=int, help='Seed the randomness for reproducible output (optional)')
    args = parser.parse_args(argv)

    src = os.path.abspath(args.env)
    if not os.path.exists(src):
        print(f"Source .env file not found: {src}")
        return 2

    if args.seed is not None:
        # seed random module for reproducibility of some operations that use it indirectly
        import random

        random.seed(args.seed)

    lines = load_env(src)

    # allow the user to override generators via environment variables like GENERATE_POSTGRES_PASSWORD=...
    # We'll check for GENERATE_<KEY>=fixed to set deterministic values
    custom_map: Dict[str, Callable[[], str]] = {}
    for env_k, env_v in os.environ.items():
        if env_k.startswith('GENERATE_') and env_v:
            key = env_k[len('GENERATE_'):]
            # If the env var value is the literal string "RANDOM" we keep random generation, else use fixed
            if env_v == 'RANDOM':
                continue
            fixed_val = env_v
            custom_map[key] = lambda v=fixed_val: v

    replacements = build_replacement_map(lines, custom_map)

    if not replacements:
        print('No sensitive keys detected to replace.')
        return 0

    new_lines = apply_replacements(lines, replacements)

    if args.dry_run or (not args.output and not args.in_place):
        print('--- Dry run: proposed replacements ---')
        for idx in sorted(replacements.keys()):
            print(f"{lines[idx].rstrip()} -> {new_lines[idx].rstrip()}")
        return 0

    out_path = os.path.abspath(args.output) if args.output else src
    if args.in_place and out_path != src:
        print('Error: --in-place specified but output path differs from source')
        return 2

    write_env(new_lines, out_path)
    print(f'Wrote updated .env to {out_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
