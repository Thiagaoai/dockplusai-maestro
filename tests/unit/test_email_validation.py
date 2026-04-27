from maestro.utils.email_validation import is_valid_email_address


def test_email_validation_rejects_malformed_csv_values():
    assert is_valid_email_address("lead@example.com")
    assert is_valid_email_address("first.last+tag@example.co")

    assert not is_valid_email_address("")
    assert not is_valid_email_address("lead@example.comlead@example.com")
    assert not is_valid_email_address("lead@example.com,other@example.com")
    assert not is_valid_email_address("lead@example")
    assert not is_valid_email_address(" lead@example.com")
