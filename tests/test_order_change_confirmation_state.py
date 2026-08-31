from copy import deepcopy

from app.data.sample_data import (
    orders,
    payments,
    payment_adjustments,
)
from app.services.orchestrator import handle_pending_state


# =========================================================
# 주문 수량 변경 최종 승인
# =========================================================

# =========================================================
# 주문 수량 증가 최종 승인
# → Write Action + 추가 결제 필요
# =========================================================

def test_order_change_confirmation_executes_write_action():

    test_orders = deepcopy(orders)
    test_payments = deepcopy(payments)
    test_adjustments = deepcopy(payment_adjustments)

    # Preview까지 끝난 상태를 직접 구성
    state = {
        "pending_action": "order_change_confirmation",
        "candidate_orders": [],
        "selected_order_id": 10007,
        "pending_data": {
            "target_quantity": 5,
            "current_quantity": 3,
            "current_total_price": 60000,
            "new_total_price": 100000,
            "adjustment_type": "additional_payment_required",
            "adjustment_amount": 40000,
        },
    }

    # -----------------------------------------------------
    # 사용자가 최종 승인
    # -----------------------------------------------------

    result = handle_pending_state(
        user_input="예",
        customer_id=6,
        orders=test_orders,
        state=state,
        payments=test_payments,
        payment_adjustments=test_adjustments,
    )

    # -----------------------------------------------------
    # Routing / Action 결과
    # -----------------------------------------------------

    assert result["route"] == "order_change"
    assert result["result"]["result_type"] == "success"

    assert result["result"]["previous_quantity"] == 3
    assert result["result"]["new_quantity"] == 5

    assert result["result"]["previous_total_price"] == 60000
    assert result["result"]["new_total_price"] == 100000

    assert (
        result["result"]["adjustment_type"]
        == "additional_payment_required"
    )

    assert result["result"]["adjustment_amount"] == 40000
    assert result["result"]["adjustment_status"] == "pending"

    # -----------------------------------------------------
    # 실제 Order 데이터 변경 확인
    # -----------------------------------------------------

    changed_order = next(
        order
        for order in test_orders
        if order["order_id"] == 10007
    )

    assert changed_order["quantity"] == 5
    assert changed_order["total_price"] == 100000

    # -----------------------------------------------------
    # 기존 결제금액은 변경하지 않음
    # -----------------------------------------------------

    payment = next(
        payment
        for payment in test_payments
        if payment["order_id"] == 10007
    )

    assert payment["payment_amount"] == 60000

    # -----------------------------------------------------
    # Payment Adjustment 생성 확인
    # -----------------------------------------------------

    assert len(test_adjustments) == 1

    adjustment = test_adjustments[0]

    assert adjustment["adjustment_id"] == 90001
    assert adjustment["order_id"] == 10007
    assert adjustment["payment_id"] == 50007

    assert (
        adjustment["adjustment_type"]
        == "additional_payment_required"
    )

    assert adjustment["adjustment_amount"] == 40000
    assert adjustment["adjustment_status"] == "pending"

    # -----------------------------------------------------
    # 작업 완료 후 State 초기화
    # -----------------------------------------------------

    assert state["pending_action"] is None
    assert state["candidate_orders"] == []
    assert state["selected_order_id"] is None
    assert state["pending_data"] == {}

    # -----------------------------------------------------
    # 사용자 응답
    # -----------------------------------------------------

    assert "주문 수량이 정상적으로 변경되었습니다" in result["response"]
    assert "이전 수량: 3개" in result["response"]
    assert "변경 수량: 5개" in result["response"]
    assert "추가 결제 필요 금액은 40,000원" in result["response"]
    assert "대기 상태" in result["response"]

# =========================================================
# 주문 수량 변경 최종 거절
# =========================================================

def test_order_change_confirmation_rejection_does_not_write():

    test_orders = deepcopy(orders)
    test_payments = deepcopy(payments)
    test_adjustments = deepcopy(payment_adjustments)

    state = {
        "pending_action": "order_change_confirmation",
        "candidate_orders": [],
        "selected_order_id": 10007,
        "pending_data": {
            "target_quantity": 2,
            "current_quantity": 3,
            "current_total_price": 60000,
            "new_total_price": 40000,
            "adjustment_type": "partial_refund_required",
            "adjustment_amount": 20000,
        },
    }

    result = handle_pending_state(
        user_input="아니오",
        customer_id=6,
        orders=test_orders,
        state=state,
        payments=test_payments,
        payment_adjustments=test_adjustments,
    )

    # 사용자 거절
    assert result["route"] == "order_change"
    assert result["result"]["result_type"] == "change_aborted"

    # 실제 주문 데이터는 변경되지 않음
    order = next(
        order
        for order in test_orders
        if order["order_id"] == 10007
    )

    assert order["quantity"] == 3
    assert order["total_price"] == 60000

    # 결제 차액도 생성되지 않음
    assert test_adjustments == []

    # 작업 종료 후 State 초기화
    assert state["pending_action"] is None
    assert state["selected_order_id"] is None
    assert state["pending_data"] == {}

    assert "진행하지 않았습니다" in result["response"]


# =========================================================
# Preview 이후 배송 시작
# → 승인해도 Action-time recheck에서 차단
# =========================================================

def test_order_change_confirmation_rechecks_state_before_write():

    test_orders = deepcopy(orders)
    test_payments = deepcopy(payments)
    test_adjustments = deepcopy(payment_adjustments)

    state = {
        "pending_action": "order_change_confirmation",
        "candidate_orders": [],
        "selected_order_id": 10007,
        "pending_data": {
            "target_quantity": 2,
            "current_quantity": 3,
            "current_total_price": 60000,
            "new_total_price": 40000,
            "adjustment_type": "partial_refund_required",
            "adjustment_amount": 20000,
        },
    }

    # Preview를 보여준 이후 배송이 시작됐다고 가정
    order = next(
        order
        for order in test_orders
        if order["order_id"] == 10007
    )

    order["delivery_status"] = "in_transit"

    # 사용자는 변경 승인
    result = handle_pending_state(
        user_input="예",
        customer_id=6,
        orders=test_orders,
        state=state,
        payments=test_payments,
        payment_adjustments=test_adjustments,
    )

    # 승인했지만 Action은 실패
    assert result["route"] == "order_change"
    assert result["result"] == {
        "result_type": "action_failed",
        "reason": "in_transit",
        "order_id": 10007,
    }

    # 실제 주문 수량/금액은 변경되지 않음
    assert order["quantity"] == 3
    assert order["total_price"] == 60000

    # 결제 차액도 생성되지 않음
    assert test_adjustments == []

    # 실패 후 State 초기화
    assert state["pending_action"] is None
    assert state["selected_order_id"] is None
    assert state["pending_data"] == {}

    assert "배송이 시작되어" in result["response"]

def test_order_change_confirmation_starts_partial_card_refund():
    from copy import deepcopy

    from app.services.orchestrator import handle_pending_state

    orders = [
        {
            "order_id": 10007,
            "customer_id": 6,
            "delivery_address": "서울시 서대문구",
            "order_date": "2026-08-13",
            "quantity": 3,
            "unit_price": 20000,
            "total_price": 60000,
            "delivery_status": "preparing_shipment",
            "order_status": "order_completed",
        }
    ]

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
    payment_adjustments = []

    state = {
        "pending_action": "order_change_confirmation",
        "candidate_orders": [],
        "selected_order_id": 10007,
        "pending_data": {
            "target_quantity": 2,
        },
    }

    test_orders = deepcopy(orders)
    test_payments = deepcopy(payments)

    result = handle_pending_state(
        user_input="예",
        customer_id=6,
        orders=test_orders,
        state=state,
        payments=test_payments,
        refunds=refunds,
        payment_adjustments=payment_adjustments,
    )

    # 주문 변경 + 환불 Flow가 모두 실행되어야 함
    assert result["route"] == "order_change"

    assert result["result"]["order_change"]["result_type"] == "success"
    assert result["result"]["refund"]["result_type"] == "success"

    # 부분 환불
    assert result["result"]["refund"]["refund_type"] == "partial"
    assert result["result"]["refund"]["refund_amount"] == 20000
    assert result["result"]["refund"]["refund_status"] == "refund_processing"

    # refunds 데이터 실제 생성
    assert len(refunds) == 1
    assert refunds[0]["order_id"] == 10007
    assert refunds[0]["refund_amount"] == 20000
    assert refunds[0]["refund_type"] == "partial"
    assert refunds[0]["refund_status"] == "refund_processing"

    # 실제 전달한 주문 데이터가 변경되었는지 확인
    assert test_orders[0]["quantity"] == 2
    assert test_orders[0]["total_price"] == 40000

    # 실제 결제 완료금액 자체는 수정하지 않음
    assert test_payments[0]["payment_amount"] == 60000

    # 카드 환불은 후속 계좌정보가 필요 없으므로 State 종료
    assert state["pending_action"] is None

# =========================================================
# 주문 수량 감소 + 계좌이체
# → 부분 환불계좌 입력 Pending State
# =========================================================

def test_order_change_confirmation_cash_refund_waits_for_account():

    test_orders = [
        {
            "order_id": 10007,
            "customer_id": 6,
            "delivery_address": "서울시 서대문구",
            "order_date": "2026-08-13",
            "quantity": 3,
            "unit_price": 20000,
            "total_price": 60000,
            "delivery_status": "preparing_shipment",
            "order_status": "order_completed",
        }
    ]

    test_payments = [
        {
            "payment_id": 50007,
            "order_id": 10007,
            "payment_amount": 60000,
            "payment_method": "cash",
            "payment_status": "payment_completed",
        }
    ]

    refunds = []
    test_adjustments = []

    state = {
        "pending_action": "order_change_confirmation",
        "candidate_orders": [],
        "selected_order_id": 10007,
        "pending_data": {
            "target_quantity": 2,
        },
    }

    result = handle_pending_state(
        user_input="예",
        customer_id=6,
        orders=test_orders,
        state=state,
        payments=test_payments,
        refunds=refunds,
        payment_adjustments=test_adjustments,
    )

    # -----------------------------------------------------
    # 주문 변경 + Refund Flow 결과
    # -----------------------------------------------------

    assert result["route"] == "order_change"

    assert (
        result["result"]["order_change"]["result_type"]
        == "success"
    )

    assert (
        result["result"]["refund"]["result_type"]
        == "refund_account_required"
    )

    assert (
        result["result"]["refund"]["refund_status"]
        == "refund_account_required"
    )

    assert result["result"]["refund"]["refund_amount"] == 20000

    # -----------------------------------------------------
    # 실제 주문 변경
    # -----------------------------------------------------

    assert test_orders[0]["quantity"] == 2
    assert test_orders[0]["total_price"] == 40000

    # 기존 실제 결제금액은 유지
    assert test_payments[0]["payment_amount"] == 60000

    # -----------------------------------------------------
    # 환불 데이터 생성
    # -----------------------------------------------------

    assert len(refunds) == 1

    assert refunds[0]["order_id"] == 10007
    assert refunds[0]["refund_type"] == "partial"
    assert refunds[0]["refund_amount"] == 20000

    assert (
        refunds[0]["refund_status"]
        == "refund_account_required"
    )

    # -----------------------------------------------------
    # Pending State 확인
    # -----------------------------------------------------

    assert (
        state["pending_action"]
        == "collect_refund_account"
    )

    assert state["selected_order_id"] == 10007

    assert (
        state["pending_data"]["refund_id"]
        == refunds[0]["refund_id"]
    )

    assert state["pending_data"]["refund_amount"] == 20000
    assert state["pending_data"]["refund_type"] == "partial"
    assert state["pending_data"]["source"] == "order_change"

    # -----------------------------------------------------
    # 사용자에게 계좌정보 요청
    # -----------------------------------------------------

    assert "환불받으실 계좌 정보를 입력해 주세요" in result["response"]