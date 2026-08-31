
from app.services.state_service import extract_refund_account


def test_extract_refund_account():

    result = extract_refund_account(
        "국민은행 / 1234567890 / 홍길동"
    )

    assert result == {
        "bank_name": "국민은행",
        "account_number": "1234567890",
        "account_holder": "홍길동",
    }


def test_invalid_refund_account_input():

    result = extract_refund_account(
        "국민은행 홍길동"
    )

    assert result is None