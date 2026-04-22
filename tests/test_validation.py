from tgbot_manage_addresslist.logic import parse_ip_input


def test_parse_ip_input_separates_valid_invalid_and_duplicates() -> None:
    result = parse_ip_input("1.1.1.1\n2.2.2.2 invalid 1.1.1.1,2001:db8::1")

    assert result.valid_ips == ["1.1.1.1", "2.2.2.2", "2001:db8::1"]
    assert result.invalid_tokens == ["invalid"]


def test_parse_ip_input_returns_empty_for_blank_input() -> None:
    result = parse_ip_input("   \n ")

    assert result.valid_ips == []
    assert result.invalid_tokens == []
