from copy import deepcopy

from app.data.sample_data import (
    orders,
    payments,
    refunds,
)

from app.services.order_payment_service import cancel_order_action

# =========================================================
# Refactored Cancel Order Action
# =========================================================

def test_cancel_order_action_only_cancels_order_and_payment():

    test_orders = deepcopy(orders)
    test_payments = deepcopy(payments)
    test_refunds = deepcopy(refunds)

    refund_count_before = len(test_refunds)

    result = cancel_order_action(
        orders=test_orders,
        payments=test_payments,
        customer_id=1,
        order_id=10001,
    )

    assert result["result_type"] == "success"
    assert result["order_status"] == "order_canceled"
    assert result["payment_status"] == "payment_canceled"

    order = next(
        order
        for order in test_orders
        if order["order_id"] == 10001
    )

    payment = next(
        payment
        for payment in test_payments
        if payment["order_id"] == 10001
    )

    assert order["order_status"] == "order_canceled"
    assert payment["payment_status"] == "payment_canceled"

    # Cancel Action은 Refund를 직접 생성하지 않는다.
    assert len(test_refunds) == refund_count_before

    # Refund 관련 결과도 반환하지 않는다.
    assert "refund_id" not in result
    assert "refund_status" not in result


def test_cancel_order_action_fails_for_invalid_order():

    test_orders = deepcopy(orders)
    test_payments = deepcopy(payments)

    result = cancel_order_action(
        orders=test_orders,
        payments=test_payments,
        customer_id=1,
        order_id=99999,
    )

    assert result["result_type"] == "action_failed"
    assert result["reason"] == "order_not_found"


def test_cancel_order_action_fails_when_payment_not_found():

    test_orders = deepcopy(orders)
    test_payments = deepcopy(payments)

    test_payments = [
        payment
        for payment in test_payments
        if payment["order_id"] != 10001
    ]

    result = cancel_order_action(
        orders=test_orders,
        payments=test_payments,
        customer_id=1,
        order_id=10001,
    )

    assert result["result_type"] == "action_failed"
    assert result["reason"] == "payment_not_found"


def test_cancel_order_action_rechecks_delivery_status():

    test_orders = deepcopy(orders)
    test_payments = deepcopy(payments)

    order = next(
        order
        for order in test_orders
        if order["order_id"] == 10001
    )

    # 최초 판단 이후 배송이 시작되었다고 가정
    order["delivery_status"] = "in_transit"

    result = cancel_order_action(
        orders=test_orders,
        payments=test_payments,
        customer_id=1,
        order_id=10001,
    )

    assert result["result_type"] == "action_failed"
    assert result["reason"] == "in_transit"

    # Action이 차단되었으므로 실제 데이터는 그대로여야 한다.
    assert order["order_status"] == "order_completed"

    payment = next(
        payment
        for payment in test_payments
        if payment["order_id"] == 10001
    )

    assert payment["payment_status"] == "payment_completed"


def test_cancel_order_action_rechecks_payment_status():

    test_orders = deepcopy(orders)
    test_payments = deepcopy(payments)

    payment = next(
        payment
        for payment in test_payments
        if payment["order_id"] == 10001
    )

    # 최초 판단 이후 결제 상태가 달라졌다고 가정
    payment["payment_status"] = "payment_canceled"

    result = cancel_order_action(
        orders=test_orders,
        payments=test_payments,
        customer_id=1,
        order_id=10001,
    )

    assert result["result_type"] == "action_failed"
    assert result["reason"] == "invalid_payment_status"

    order = next(
        order
        for order in test_orders
        if order["order_id"] == 10001
    )

    # Action이 차단되었으므로 주문 상태도 변경되면 안 된다.
    assert order["order_status"] == "order_completed"