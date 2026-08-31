from copy import deepcopy

from app.data.sample_data import (
    orders,
    payments,
    payment_adjustments,
)
from app.services.orchestrator import route_request


# =========================================================
# 주문 수량 감소 + 카드 부분환불 E2E
# =========================================================

def test_order_change_partial_card_refund_full_e2e():

    test_orders = deepcopy(orders)
    test_payments = deepcopy(payments)
    test_adjustments = deepcopy(payment_adjustments)
    test_refunds = []

    test_state = {
        "pending_action": None,
        "candidate_orders": [],
        "selected_order_id": None,
        "pending_data": {},
    }

    # 테스트 대상 주문
    order = next(
        order
        for order in test_orders
        if order["order_id"] == 10007
    )

    payment = next(
        payment
        for payment in test_payments
        if payment["order_id"] == 10007
    )

    # =====================================================
    # 1턴: 주문 수량 감소 요청
    # =====================================================

    first_result = route_request(
        user_input="10007번 주문 1개 줄여줘",
        customer_id=6,
        orders=test_orders,
        state=test_state,
        payments=test_payments,
        refunds=test_refunds,
        payment_adjustments=test_adjustments,
    )

    assert first_result["route"] == "order_change"

    assert (
        first_result["result"]["result_type"]
        == "change_preview"
    )

    calculation = first_result["result"]["calculation"]

    assert calculation["current_quantity"] == 3
    assert calculation["target_quantity"] == 2

    assert calculation["current_total_price"] == 60000
    assert calculation["new_total_price"] == 40000

    assert (
        calculation["adjustment_type"]
        == "partial_refund_required"
    )

    assert calculation["adjustment_amount"] == 20000

    # -----------------------------------------------------
    # 승인 전에는 실제 데이터 변경 X
    # -----------------------------------------------------

    assert order["quantity"] == 3
    assert order["total_price"] == 60000

    assert payment["payment_amount"] == 60000

    assert test_adjustments == []
    assert test_refunds == []

    assert (
        test_state["pending_action"]
        == "order_change_confirmation"
    )

    assert test_state["selected_order_id"] == 10007
    assert test_state["pending_data"]["target_quantity"] == 2

    # =====================================================
    # 2턴: 사용자 최종 승인
    # =====================================================

    second_result = route_request(
        user_input="예",
        customer_id=6,
        orders=test_orders,
        state=test_state,
        payments=test_payments,
        refunds=test_refunds,
        payment_adjustments=test_adjustments,
    )

    assert second_result["route"] == "order_change"

    # -----------------------------------------------------
    # Order Change 결과
    # -----------------------------------------------------

    order_change_result = second_result["result"]["order_change"]

    assert order_change_result["result_type"] == "success"
    assert order_change_result["previous_quantity"] == 3
    assert order_change_result["new_quantity"] == 2
    assert order_change_result["previous_total_price"] == 60000
    assert order_change_result["new_total_price"] == 40000

    assert (
        order_change_result["adjustment_type"]
        == "partial_refund_required"
    )

    assert order_change_result["adjustment_amount"] == 20000

    # -----------------------------------------------------
    # 실제 Order Write 확인
    # -----------------------------------------------------

    assert order["quantity"] == 2
    assert order["total_price"] == 40000

    # 기존 실제 결제금액은 그대로 유지
    assert payment["payment_amount"] == 60000

    # -----------------------------------------------------
    # Payment Adjustment 확인
    # -----------------------------------------------------

    assert len(test_adjustments) == 1

    adjustment = test_adjustments[0]

    assert adjustment["order_id"] == 10007
    assert adjustment["payment_id"] == 50007

    assert (
        adjustment["adjustment_type"]
        == "partial_refund_required"
    )

    assert adjustment["adjustment_amount"] == 20000
    assert adjustment["adjustment_status"] == "pending"

    # -----------------------------------------------------
    # Refund Flow 확인
    # -----------------------------------------------------

    refund_result = second_result["result"]["refund"]

    assert refund_result["result_type"] == "success"
    assert refund_result["refund_type"] == "partial"
    assert refund_result["refund_amount"] == 20000
    assert refund_result["refund_status"] == "refund_processing"

    # 실제 refunds 데이터 생성
    assert len(test_refunds) == 1

    refund = test_refunds[0]

    assert refund["order_id"] == 10007
    assert refund["payment_id"] == 50007
    assert refund["refund_type"] == "partial"
    assert refund["refund_amount"] == 20000
    assert refund["refund_status"] == "refund_processing"

    # -----------------------------------------------------
    # 카드 환불은 계좌 입력이 필요 없으므로 State 종료
    # -----------------------------------------------------

    assert test_state["pending_action"] is None
    assert test_state["candidate_orders"] == []
    assert test_state["selected_order_id"] is None
    assert test_state["pending_data"] == {}

    assert "카드 부분 환불 절차를 시작했습니다" in second_result["response"]
    assert "현재 환불 처리 중입니다" in second_result["response"]

# =========================================================
# 주문 수량 증가 E2E
# =========================================================

def test_order_change_increase_full_e2e():

    test_orders = deepcopy(orders)
    test_payments = deepcopy(payments)
    test_adjustments = deepcopy(payment_adjustments)

    test_state = {
        "pending_action": None,
        "candidate_orders": [],
        "selected_order_id": None,
        "pending_data": {},
    }

    order = next(
        order
        for order in test_orders
        if order["order_id"] == 10007
    )

    payment = next(
        payment
        for payment in test_payments
        if payment["order_id"] == 10007
    )

    # =====================================================
    # 1턴: 2개 추가 요청
    # =====================================================

    first_result = route_request(
        user_input="10007번 주문 2개 더 추가해줘",
        customer_id=6,
        orders=test_orders,
        state=test_state,
        payments=test_payments,
        payment_adjustments=test_adjustments,
    )

    assert first_result["route"] == "order_change"
    assert (
        first_result["result"]["result_type"]
        == "change_preview"
    )

    calculation = first_result["result"]["calculation"]

    assert calculation["current_quantity"] == 3
    assert calculation["target_quantity"] == 5

    assert calculation["current_total_price"] == 60000
    assert calculation["new_total_price"] == 100000

    assert (
        calculation["adjustment_type"]
        == "additional_payment_required"
    )

    assert calculation["adjustment_amount"] == 40000

    # 승인 전에는 실제 데이터 변경 X
    assert order["quantity"] == 3
    assert order["total_price"] == 60000
    assert payment["payment_amount"] == 60000
    assert test_adjustments == []

    assert (
        test_state["pending_action"]
        == "order_change_confirmation"
    )

    # =====================================================
    # 2턴: 최종 승인
    # =====================================================

    second_result = route_request(
        user_input="예",
        customer_id=6,
        orders=test_orders,
        state=test_state,
        payments=test_payments,
        payment_adjustments=test_adjustments,
    )

    assert second_result["route"] == "order_change"
    assert second_result["result"]["result_type"] == "success"

    # 실제 주문 변경
    assert order["quantity"] == 5
    assert order["total_price"] == 100000

    # 이미 결제된 금액은 그대로
    assert payment["payment_amount"] == 60000

    # 추가 결제 필요 데이터 생성
    assert len(test_adjustments) == 1

    adjustment = test_adjustments[0]

    assert (
        adjustment["adjustment_type"]
        == "additional_payment_required"
    )

    assert adjustment["adjustment_amount"] == 40000
    assert adjustment["adjustment_status"] == "pending"

    # 완료 후 State 초기화
    assert test_state["pending_action"] is None
    assert test_state["candidate_orders"] == []
    assert test_state["selected_order_id"] is None
    assert test_state["pending_data"] == {}


# =========================================================
# 수량 0 요청 E2E
# → 자동 주문 취소 금지
# =========================================================

def test_order_change_zero_quantity_does_not_cancel_order():

    test_orders = deepcopy(orders)
    test_payments = deepcopy(payments)
    test_adjustments = deepcopy(payment_adjustments)

    test_state = {
        "pending_action": None,
        "candidate_orders": [],
        "selected_order_id": None,
        "pending_data": {},
    }

    order = next(
        order
        for order in test_orders
        if order["order_id"] == 10007
    )

    # =====================================================
    # 수량을 0개로 변경 요청
    # =====================================================

    result = route_request(
        user_input="10007번 주문 수량을 0개로 바꿔줘",
        customer_id=6,
        orders=test_orders,
        state=test_state,
        payments=test_payments,
        payment_adjustments=test_adjustments,
    )

    assert result["route"] == "order_change"

    assert (
        result["result"]["result_type"]
        == "cancel_required"
    )

    # -----------------------------------------------------
    # order_change가 주문 취소를 자동 실행하면 안 됨
    # -----------------------------------------------------

    assert order["quantity"] == 3
    assert order["total_price"] == 60000

    assert order["order_status"] == "order_completed"

    # Payment Adjustment도 생성 X
    assert test_adjustments == []

    # order_change 흐름은 종료
    assert test_state["pending_action"] is None
    assert test_state["candidate_orders"] == []
    assert test_state["selected_order_id"] is None
    assert test_state["pending_data"] == {}

    assert "주문 취소가 필요합니다" in result["response"]

# =========================================================
# 주문 수량 감소 + 계좌이체 부분환불 E2E
# =========================================================

def test_order_change_partial_cash_refund_full_e2e():

    test_orders = deepcopy(orders)
    test_payments = deepcopy(payments)
    test_adjustments = deepcopy(payment_adjustments)
    test_refunds = []

    test_state = {
        "pending_action": None,
        "candidate_orders": [],
        "selected_order_id": None,
        "pending_data": {},
    }

    order = next(
        order
        for order in test_orders
        if order["order_id"] == 10007
    )

    payment = next(
        payment
        for payment in test_payments
        if payment["order_id"] == 10007
    )

    # 테스트를 위해 계좌이체 결제로 변경
    payment["payment_method"] = "cash"

    # =====================================================
    # 1턴: 주문 수량 감소 요청
    # =====================================================

    first_result = route_request(
        user_input="10007번 주문 1개 줄여줘",
        customer_id=6,
        orders=test_orders,
        state=test_state,
        payments=test_payments,
        refunds=test_refunds,
        payment_adjustments=test_adjustments,
    )

    assert first_result["route"] == "order_change"

    assert (
        first_result["result"]["result_type"]
        == "change_preview"
    )

    calculation = first_result["result"]["calculation"]

    assert calculation["target_quantity"] == 2
    assert calculation["new_total_price"] == 40000

    assert (
        calculation["adjustment_type"]
        == "partial_refund_required"
    )

    assert calculation["adjustment_amount"] == 20000

    # 아직 승인 전
    assert order["quantity"] == 3
    assert test_refunds == []

    assert (
        test_state["pending_action"]
        == "order_change_confirmation"
    )

    # =====================================================
    # 2턴: 수량 변경 최종 승인
    # =====================================================

    second_result = route_request(
        user_input="예",
        customer_id=6,
        orders=test_orders,
        state=test_state,
        payments=test_payments,
        refunds=test_refunds,
        payment_adjustments=test_adjustments,
    )

    assert second_result["route"] == "order_change"

    order_change_result = second_result["result"]["order_change"]
    refund_result = second_result["result"]["refund"]

    # 실제 주문 변경
    assert order_change_result["result_type"] == "success"

    assert order["quantity"] == 2
    assert order["total_price"] == 40000

    # 기존 결제금액은 그대로
    assert payment["payment_amount"] == 60000

    # 부분환불 필요
    assert refund_result["refund_type"] == "partial"
    assert refund_result["refund_amount"] == 20000

    # 계좌이체라 계좌정보가 필요함
    assert (
        refund_result["result_type"]
        == "refund_account_required"
    )

    assert (
        refund_result["refund_status"]
        == "refund_account_required"
    )

    # 실제 Refund 데이터 생성
    assert len(test_refunds) == 1

    refund = test_refunds[0]

    assert refund["refund_amount"] == 20000
    assert refund["refund_type"] == "partial"

    assert (
        refund["refund_status"]
        == "refund_account_required"
    )

    # -----------------------------------------------------
    # 다음 턴을 위한 Pending State
    # -----------------------------------------------------

    assert (
        test_state["pending_action"]
        == "collect_refund_account"
    )

    assert test_state["selected_order_id"] == 10007

    refund_id = refund["refund_id"]

    assert (
        test_state["pending_data"]["refund_id"]
        == refund_id
    )

    # =====================================================
    # 3턴: 환불계좌 입력
    # =====================================================

    third_result = route_request(
        user_input="국민은행 / 1234567890 / 홍길동",
        customer_id=6,
        orders=test_orders,
        state=test_state,
        payments=test_payments,
        refunds=test_refunds,
        payment_adjustments=test_adjustments,
    )

    assert third_result["route"] == "order_change"

    assert third_result["result"]["result_type"] == "success"

    assert third_result["result"]["refund_id"] == refund_id

    assert (
        third_result["result"]["refund_status"]
        == "refund_processing"
    )

    # -----------------------------------------------------
    # 실제 Refund 데이터에 계좌정보 저장
    # -----------------------------------------------------

    assert refund["bank_name"] == "국민은행"
    assert refund["account_number"] == "1234567890"
    assert refund["account_holder"] == "홍길동"

    assert (
        refund["refund_status"]
        == "refund_processing"
    )

    # -----------------------------------------------------
    # 모든 Multi-turn 작업 종료
    # -----------------------------------------------------

    assert test_state["pending_action"] is None
    assert test_state["candidate_orders"] == []
    assert test_state["selected_order_id"] is None
    assert test_state["pending_data"] == {}

    assert "환불계좌가 정상적으로 등록되었습니다" in third_result["response"]
    assert "20,000원" in third_result["response"]
    assert "환불 처리 중" in third_result["response"]