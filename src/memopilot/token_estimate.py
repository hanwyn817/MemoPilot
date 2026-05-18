from __future__ import annotations


def estimate_tokens(text: str) -> int:
    ascii_chars = sum(1 for char in text if ord(char) < 128)
    non_ascii_chars = len(text) - ascii_chars
    return int(non_ascii_chars * 1.1 + ascii_chars / 4) + 1

