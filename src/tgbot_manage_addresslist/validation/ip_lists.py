from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
import re


TOKEN_SPLIT_RE = re.compile(r"[\s,;]+")


@dataclass(frozen=True, slots=True)
class ParsedIpInput:
    valid_ips: list[str]
    invalid_tokens: list[str]


def parse_ip_input(raw_text: str) -> ParsedIpInput:
    valid_ips: list[str] = []
    invalid_tokens: list[str] = []
    seen: set[str] = set()

    for token in TOKEN_SPLIT_RE.split(raw_text.strip()):
        if not token:
            continue
        try:
            normalized = str(ip_address(token))
        except ValueError:
            invalid_tokens.append(token)
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        valid_ips.append(normalized)

    return ParsedIpInput(valid_ips=valid_ips, invalid_tokens=invalid_tokens)
