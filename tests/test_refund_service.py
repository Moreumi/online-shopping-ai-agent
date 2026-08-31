from app.services.refund_service import start_refund


# =========================================================
# 1. 카드 부분 환불
# =========================================================

def test_start_partial_refund_card():
    payments = [
        {
            "payment_id": 50007,
            "order_id": 10007,
            "payment_amount": 60000,
            "payment_method": "card",
            "payment_status": "payment_completed",
        }
    ]

    refunds = []

    result = start_refund(
        payments=payments,
        refunds=refunds,
        order_id=10007,
        refund_amount=20000,
        refund_type="partial",
        refund_reason="order_quantity_decrease",
        adjustment_id=90001,
    )

    assert result["result_type"] == "success"
    assert result["refund_status"] == "refund_processing"
    assert result["refund_amount"] == 20000
    assert result["refund_type"] == "partial"
    assert result["adjustment_id"] == 90001

    assert len(refunds) == 1
    assert refunds[0]["refund_amount"] == 20000
    assert refunds[0]["refund_status"] == "refund_processing"


# =========================================================
# 2. 계좌이체 부분 환불
# =========================================================

def test_start_partial_refund_cash_requires_account():
    payments = [
        {
            "payment_id": 50007,
            "order_id": 10007,
            "payment_amount": 60000,
            "payment_method": "cash",
            "payment_status": "payment_completed",
        }
    ]

    refunds = []

    result = start_refund(
        payments=payments,
        refunds=refunds,
        order_id=10007,
        refund_amount=20000,
        refund_type="partial",
        refund_reason="order_quantity_decrease",
        adjustment_id=90001,
    )

    assert result["result_type"] == "refund_account_required"
    assert result["refund_status"] == "refund_account_required"

    assert len(refunds) == 1
    assert refunds[0]["bank_name"] is None
    assert refunds[0]["account_number"] is None
    assert refunds[0]["account_holder"] is None


# =========================================================
# 3. 결제정보 없음
# =========================================================

def test_start_refund_payment_not_found():
    result = start_refund(
        payments=[],
        refunds=[],
        order_id=10007,
        refund_amount=20000,
        refund_type="partial",
        refund_reason="order_quantity_decrease",
    )

    assert result["result_type"] == "action_failed"
    assert result["reason"] == "payment_not_found"


# =========================================================
# 4. 잘못된 환불금액
# =========================================================

def test_start_refund_invalid_amount():
    payments = [
        {
            "payment_id": 50007,
            "order_id": 10007,
            "payment_amount": 60000,
            "payment_method": "card",
            "payment_status": "payment_completed",
        }
    ]

    result = start_refund(
        payments=payments,
        refunds=[],
        order_id=10007,
        refund_amount=0,
        refund_type="partial",
        refund_reason="order_quantity_decrease",
    )

    assert result["result_type"] == "action_failed"
    assert result["reason"] == "invalid_refund_amount"


# =========================================================
# 5. 실제 결제금액보다 큰 환불
# =========================================================

def test_start_refund_amount_exceeds_payment():
    payments = [
        {
            "payment_id": 50007,
            "order_id": 10007,
            "payment_amount": 60000,
            "payment_method": "card",
            "payment_status": "payment_completed",
        }
    ]

    result = start_refund(
        payments=payments,
        refunds=[],
        order_id=10007,
        refund_amount=70000,
        refund_type="partial",
        refund_reason="order_quantity_decrease",
    )

    assert result["result_type"] == "action_failed"
    assert result["reason"] == "refund_amount_exceeds_payment"

    # =========================================================
# 6. 환불계좌 정상 등록
# =========================================================

def test_register_refund_account_success():
    from app.services.refund_service import register_refund_account

    refunds = [
        {
            "refund_id": 70001,
            "payment_id": 50007,
            "order_id": 10007,
            "refund_type": "partial",
            "refund_amount": 20000,
            "refund_reason": "order_quantity_decrease",
            "refund_status": "refund_account_required",
            "adjustment_id": 90001,
            "bank_name": None,
            "account_number": None,
            "account_holder": None,
        }
    ]

    result = register_refund_account(
        refunds=refunds,
        refund_id=70001,
        bank_name="국민은행",
        account_number="1234567890",
        account_holder="홍길동",
    )

    assert result["result_type"] == "success"
    assert result["refund_status"] == "refund_processing"

    assert refunds[0]["bank_name"] == "국민은행"
    assert refunds[0]["account_number"] == "1234567890"
    assert refunds[0]["account_holder"] == "홍길동"
    assert refunds[0]["refund_status"] == "refund_processing"


# =========================================================
# 7. 존재하지 않는 refund_id
# =========================================================

def test_register_refund_account_refund_not_found():
    from app.services.refund_service import register_refund_account

    result = register_refund_account(
        refunds=[],
        refund_id=70001,
        bank_name="국민은행",
        account_number="1234567890",
        account_holder="홍길동",
    )

    assert result["result_type"] == "action_failed"
    assert result["reason"] == "refund_not_found"


# =========================================================
# 8. 이미 처리 중인 환불 건
# =========================================================

def test_register_refund_account_invalid_refund_status():
    from app.services.refund_service import register_refund_account

    refunds = [
        {
            "refund_id": 70001,
            "payment_id": 50007,
            "order_id": 10007,
            "refund_type": "partial",
            "refund_amount": 20000,
            "refund_reason": "order_quantity_decrease",
            "refund_status": "refund_processing",
            "adjustment_id": 90001,
            "bank_name": None,
            "account_number": None,
            "account_holder": None,
        }
    ]

    result = register_refund_account(
        refunds=refunds,
        refund_id=70001,
        bank_name="국민은행",
        account_number="1234567890",
        account_holder="홍길동",
    )

    assert result["result_type"] == "action_failed"
    assert result["reason"] == "invalid_refund_status"

# =========================================================
# validate_refund_request
# =========================================================

def test_validate_full_refund_resolves_payment_amount():
    from app.services.refund_service import validate_refund_request

    payments = [
        {
            "payment_id": 50001,
            "order_id": 10001,
            "payment_amount": 60000,
            "payment_method": "card",
            "payment_status": "payment_completed",
        }
    ]

    result = validate_refund_request(
        payments=payments,
        order_id=10001,
        refund_type="full",
        refund_amount=None,
    )

    assert result["result_type"] == "success"
    assert result["refund_type"] == "full"
    assert result["refund_amount"] == 60000
    assert result["payment_method"] == "card"


def test_validate_partial_refund_uses_requested_amount():
    from app.services.refund_service import validate_refund_request

    payments = [
        {
            "payment_id": 50001,
            "order_id": 10001,
            "payment_amount": 60000,
            "payment_method": "card",
            "payment_status": "payment_completed",
        }
    ]

    result = validate_refund_request(
        payments=payments,
        order_id=10001,
        refund_type="partial",
        refund_amount=20000,
    )

    assert result["result_type"] == "success"
    assert result["refund_type"] == "partial"
    assert result["refund_amount"] == 20000


def test_validate_refund_rejects_invalid_refund_type():
    from app.services.refund_service import validate_refund_request

    payments = [
        {
            "payment_id": 50001,
            "order_id": 10001,
            "payment_amount": 60000,
            "payment_method": "card",
            "payment_status": "payment_completed",
        }
    ]

    result = validate_refund_request(
        payments=payments,
        order_id=10001,
        refund_type="invalid",
        refund_amount=20000,
    )

    assert result["result_type"] == "action_failed"
    assert result["reason"] == "invalid_refund_type"


def test_validate_refund_rejects_unsupported_payment_method():
    from app.services.refund_service import validate_refund_request

    payments = [
        {
            "payment_id": 50001,
            "order_id": 10001,
            "payment_amount": 60000,
            "payment_method": "unsupported",
            "payment_status": "payment_completed",
        }
    ]

    result = validate_refund_request(
        payments=payments,
        order_id=10001,
        refund_type="full",
        refund_amount=None,
    )

    assert result["result_type"] == "action_failed"
    assert result["reason"] == "unsupported_payment_method"