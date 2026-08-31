from app.services.orchestrator import handle_pending_state


# =========================================================
# 주문 수량 감소 후 부분 환불계좌 입력
# =========================================================

def test_partial_refund_account_input_continues_pending_flow():

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

    state = {
        "pending_action": "collect_refund_account",
        "candidate_orders": [],
        "selected_order_id": 10007,
        "pending_data": {
            "refund_id": 70001,
            "refund_amount": 20000,
            "refund_type": "partial",
            "source": "order_change",
        },
    }

    result = handle_pending_state(
        user_input="국민은행 / 1234567890 / 홍길동",
        customer_id=6,
        orders=[],
        state=state,
        payments=[],
        refunds=refunds,
        payment_adjustments=[],
    )

    # -----------------------------------------------------
    # Routing / 처리 결과
    # -----------------------------------------------------

    assert result["route"] == "order_change"

    assert result["result"]["result_type"] == "success"
    assert result["result"]["refund_id"] == 70001
    assert result["result"]["order_id"] == 10007
    assert result["result"]["refund_amount"] == 20000

    assert (
        result["result"]["refund_status"]
        == "refund_processing"
    )

    # -----------------------------------------------------
    # 실제 Refund 데이터 변경
    # -----------------------------------------------------

    assert refunds[0]["bank_name"] == "국민은행"
    assert refunds[0]["account_number"] == "1234567890"
    assert refunds[0]["account_holder"] == "홍길동"

    assert (
        refunds[0]["refund_status"]
        == "refund_processing"
    )

    # -----------------------------------------------------
    # 작업 완료 후 Pending State 초기화
    # -----------------------------------------------------

    assert state["pending_action"] is None
    assert state["candidate_orders"] == []
    assert state["selected_order_id"] is None
    assert state["pending_data"] == {}

    # -----------------------------------------------------
    # 사용자 응답
    # -----------------------------------------------------

    assert "환불계좌가 정상적으로 등록되었습니다" in result["response"]
    assert "20,000원" in result["response"]
    assert "환불 처리 중" in result["response"]