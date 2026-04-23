from __future__ import annotations

from tgbot_manage_addresslist.logic import parse_ip_input


def test_parse_ip_input_accepts_cidr_networks() -> None:
    parsed = parse_ip_input(
        "\n".join(
            [
                "149.154.164.0/22",
                "149.154.160.0/20",
                "91.108.8.0/22",
            ]
        )
    )

    assert parsed.valid_ips == [
        "149.154.164.0/22",
        "149.154.160.0/20",
        "91.108.8.0/22",
    ]
    assert parsed.invalid_tokens == []
