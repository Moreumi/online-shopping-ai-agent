from copy import deepcopy

from app.data.sample_data import (
    orders,
    payments,
    refunds,
)

from app.services.orchestrator import handle_pending_state


def prepare_refund_account_state():

    test_orders = deepcopy(orders)
    test_payments = deepcopy(payments)
    test_refunds = deepcopy(refunds)

    # -----------------------------------------------------
    # 주문 취소 최종 승인 상태 준비
    # -----------------------------------------------------

    test_state = {
        "pending_action": "confirm_cancel",
        "candidate_orders": [],
        "selected_order_id": 10006,
        "pending_data": {},
    }

    # -----------------------------------------------------
    # 실제 새 Order Cancel Flow 실행
    #
    # confirm_cancel
    # → Refund 사전 검증
    # → cancel_order_action
    # → start_refund
    # → collect_refund_account
    # -----------------------------------------------------

    cancel_result = handle_pending_state(
        user_input="예",
        customer_id=5,
        orders=test_orders,
        payments=test_payments,
        refunds=test_refunds,
        state=test_state,
    )

    assert (
        cancel_result["result"]["refund_status"]
        == "refund_account_required"
    )

    # 공통 Refund Pending Flow로 이동했는지 확인
    assert (
        test_state["pending_action"]
        == "collect_refund_account"
    )

    assert test_state["selected_order_id"] == 10006

    # 공통 Handler가 사용할 Refund Context 확인
    assert test_state["pending_data"]["refund_id"] is not None
    assert test_state["pending_data"]["refund_type"] == "full"
    assert test_state["pending_data"]["source"] == "order_cancel"

    return (
        test_orders,
        test_payments,
        test_refunds,
        test_state,
    )


def test_refund_account_multiturn_success():

    (
        test_orders,
        test_payments,
        test_refunds,
        test_state,
    ) = prepare_refund_account_state()

    result = handle_pending_state(
        user_input="국민은행 / 1234567890 / 홍길동",
        customer_id=5,
        orders=test_orders,
        payments=test_payments,
        refunds=test_refunds,
        state=test_state,
    )

    assert result["route"] == "order_cancel"
    assert result["result"]["result_type"] == "success"
    assert result["result"]["refund_status"] == "refund_processing"

    refund = next(
        refund
        for refund in test_refunds
        if refund["order_id"] == 10006
    )

    assert refund["bank_name"] == "국민은행"
    assert refund["account_number"] == "1234567890"
    assert refund["account_holder"] == "홍길동"
    assert refund["refund_status"] == "refund_processing"

    # 작업이 끝났으므로 State 초기화
    assert test_state["pending_action"] is None
    assert test_state["selected_order_id"] is None
    assert test_state["pending_data"] == {}

def test_invalid_refund_account_keeps_state():

    (
        test_orders,
        test_payments,
        test_refunds,
        test_state,
    ) = prepare_refund_account_state()

    result = handle_pending_state(
        user_input="국민은행 홍길동",
        customer_id=5,
        orders=test_orders,
        payments=test_payments,
        refunds=test_refunds,
        state=test_state,
    )

    assert result["result"] is None

    # 잘못 입력했다고 환불 작업을 끝내면 안 됨
    assert test_state["pending_action"] == "collect_refund_account"
    assert test_state["selected_order_id"] == 10006

    refund = next(
        refund
        for refund in test_refunds
        if refund["order_id"] == 10006
    )

    # 실제 환불 상태 역시 아직 바뀌면 안 됨
    assert refund["refund_status"] == "refund_account_required"