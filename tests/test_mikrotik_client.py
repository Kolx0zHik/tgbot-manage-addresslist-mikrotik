from tgbot_manage_addresslist.mikrotik import (
    parse_address_list_names,
    parse_addresses,
    routeros_quote,
)


def test_parse_address_list_names_collects_unique_names() -> None:
    output = """
0 list=GERMANY address=1.1.1.1
1 list=GERMANY address=2.2.2.2
2 list=OFFICE address=3.3.3.3
"""

    assert parse_address_list_names(output) == ["GERMANY", "OFFICE"]


def test_parse_addresses_reads_routeros_output() -> None:
    output = """
0 list=GERMANY address=1.1.1.1
1 list=GERMANY address=2.2.2.2
"""

    assert parse_addresses(output) == ["1.1.1.1", "2.2.2.2"]


def test_routeros_quote_escapes_backslashes_and_quotes() -> None:
    assert routeros_quote('name "with" \\ slash') == '"name \\"with\\" \\\\ slash"'
