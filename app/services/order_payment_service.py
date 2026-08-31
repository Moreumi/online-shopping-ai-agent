from app.policies.order_completion_policy import judge_order_completion
from app.policies.payment_completion_policy import judge_payment_completion
from app.policies.order_cancel_policy import judge_order_cancel

from app.policies.order_payment_consistency_policy import (
    judge_order_payment_consistency,
)

from app.policies.delivery_address_change_policy import (
    judge_delivery_address_change,
)

from app.policies.order_change_policy import judge_order_change

# =========================================================
# 주문 완료 상태 확인
# =========================================================

def check_order_completion(
    orders: list[dict],
    customer_id: int,
    order_id: int | None = None
) -> dict:

    # 해당 고객의 주문만 조회
    customer_orders = [
        order
        for order in orders
        if order["customer_id"] == customer_id
    ]

    # 해당 고객의 주문이 없는 경우
    if not customer_orders:
        return {
            "result_type": "not_found"
        }

    # 주문번호가 제공된 경우
    if order_id is not None:

        matched_orders = [
            order
            for order in customer_orders
            if order["order_id"] == order_id
        ]

        if not matched_orders:
            return {
                "result_type": "not_found"
            }

        order = matched_orders[0]

        return {
            "result_type": "success",
            "judgment": judge_order_completion(order["order_status"]),
            "order_id": order["order_id"],
            "order_status": order["order_status"],
            "order_date": order["order_date"],
            "total_price": order["total_price"]
        }

    # 주문번호가 없고 해당 고객 주문이 한 건인 경우
    if len(customer_orders) == 1:

        order = customer_orders[0]

        return {
            "result_type": "success",
            "judgment": judge_order_completion(order["order_status"]),
            "order_id": order["order_id"],
            "order_status": order["order_status"],
            "order_date": order["order_date"],
            "total_price": order["total_price"]
        }

    # 주문번호가 없고 해당 고객 주문이 여러 건인 경우
    return {
        "result_type": "need_order_selection",
        "candidate_orders": [
            {
                "order_id": order["order_id"],
                "order_date": order["order_date"],
                "total_price": order["total_price"]
            }
            for order in customer_orders
        ]
    }


# =========================================================
# 주문 취소 가능 여부 확인
# =========================================================

def check_order_cancel_eligibility(
    orders: list[dict],
    customer_id: int,
    order_id: int | None = None,
) -> dict:
    """
    고객의 주문을 조회한 뒤
    Order Cancel Policy를 사용하여 주문 취소 가능 여부를 판단한다.

    실제 주문 취소 Action은 수행하지 않는다.
    """

    # -----------------------------------------------------
    # 1. 해당 고객의 주문만 조회

    customer_orders = [
        order
        for order in orders
        if order["customer_id"] == customer_id
    ]

    # 고객의 주문이 없는 경우
    if not customer_orders:
        return {
            "result_type": "not_found",
        }

    # -----------------------------------------------------
    # 2. 사용자가 주문번호를 직접 입력한 경우

    if order_id is not None:
        selected_order = next(
            (
                order
                for order in customer_orders
                if order["order_id"] == order_id
            ),
            None,
        )

        # 해당 고객의 주문이 아닌 경우
        if selected_order is None:
            return {
                "result_type": "not_found",
            }

    # -----------------------------------------------------
    # 3. 주문번호가 없는 경우

    else:
        # 주문이 여러 건이면 사용자가 선택해야 함
        if len(customer_orders) > 1:
            return {
                "result_type": "need_order_selection",
                "candidate_orders": [
                    {
                        "order_id": order["order_id"],
                        "order_date": order["order_date"],
                        "total_price": order["total_price"],
                    }
                    for order in customer_orders
                ],
            }

        # 주문이 한 건이면 자동 선택
        selected_order = customer_orders[0]

    # -----------------------------------------------------
    # 4. 주문 취소 가능 여부 Policy 판단

    cancel_result = judge_order_cancel(
        order_status=selected_order["order_status"],
        delivery_status=selected_order["delivery_status"],
    )

    # -----------------------------------------------------
    # 5. 조회 결과 + Policy 결과 반환

    return {
        "result_type": "success",
        "order_id": selected_order["order_id"],
        "order_status": selected_order["order_status"],
        "delivery_status": selected_order["delivery_status"],
        "order_date": selected_order["order_date"],
        "total_price": selected_order["total_price"],
        "cancel_judgment": cancel_result["cancel_judgment"],
        "reason": cancel_result["reason"],
    }


# =========================================================
# 배송지 변경 가능 여부 확인
# =========================================================

def check_delivery_address_change_eligibility(
    orders: list[dict],
    customer_id: int,
    order_id: int | None = None,
) -> dict:
    """
    고객의 주문을 조회한 뒤
    Delivery Address Change Policy를 사용하여
    배송지 변경 가능 여부를 판단한다.

    실제 배송지 변경 Action은 수행하지 않는다.
    """

    # 1. 해당 고객의 주문만 조회

    customer_orders = [
        order
        for order in orders
        if order["customer_id"] == customer_id
    ]

    if not customer_orders:
        return {
            "result_type": "not_found",
        }

    # 2. 주문번호가 직접 제공된 경우

    if order_id is not None:
        selected_order = next(
            (
                order
                for order in customer_orders
                if order["order_id"] == order_id
            ),
            None,
        )

        if selected_order is None:
            return {
                "result_type": "not_found",
            }

    # 3. 주문번호가 없는 경우

    else:
        # 여러 주문이 있으면 사용자가 선택해야 함
        if len(customer_orders) > 1:
            return {
                "result_type": "need_order_selection",
                "candidate_orders": [
                    {
                        "order_id": order["order_id"],
                        "order_date": order["order_date"],
                        "total_price": order["total_price"],
                        "delivery_address": order["delivery_address"],
                    }
                    for order in customer_orders
                ],
            }

        # 주문이 한 건이면 자동 선택
        selected_order = customer_orders[0]

    # 4. 배송지 변경 가능 여부 Policy 판단

    address_change_result = judge_delivery_address_change(
        order_status=selected_order["order_status"],
        delivery_status=selected_order["delivery_status"],
    )

    # 5. 조회 결과 + Policy 결과 반환

    return {
        "result_type": "success",
        "order_id": selected_order["order_id"],
        "order_status": selected_order["order_status"],
        "delivery_status": selected_order["delivery_status"],
        "delivery_address": selected_order["delivery_address"],
        "order_date": selected_order["order_date"],
        "total_price": selected_order["total_price"],
        "address_change_judgment": (
            address_change_result["address_change_judgment"]
        ),
        "reason": address_change_result["reason"],
    }

# =========================================================
# 주문 수량 변경 계산
# =========================================================

def calculate_order_quantity_change(
    current_quantity: int,
    quantity_change_type: str,
    quantity_value: int,
    unit_price: int,
    current_total_price: int,
) -> dict:
    """
    사용자의 수량 변경 요청을 기준으로
    목표 수량, 변경 후 주문금액, 결제 차액을 계산한다.

    실제 주문 데이터나 결제 데이터는 수정하지 않는다.
    """

    # 1. 현재 데이터 기본 검증

    if current_quantity <= 0:
        return {
            "result_type": "invalid_data",
            "reason": "invalid_current_quantity",
        }

    if unit_price <= 0:
        return {
            "result_type": "invalid_data",
            "reason": "invalid_unit_price",
        }

    if quantity_value < 0:
        return {
            "result_type": "invalid_quantity",
            "reason": "negative_quantity_value",
        }

    # 현재 수량 × 단가와 저장된 주문금액이 일치하는지 확인
    expected_current_total = current_quantity * unit_price

    if current_total_price != expected_current_total:
        return {
            "result_type": "data_inconsistent",
            "reason": "total_price_mismatch",
            "current_quantity": current_quantity,
            "unit_price": unit_price,
            "current_total_price": current_total_price,
            "expected_total_price": expected_current_total,
        }

    # 2. 목표 수량 계산

    if quantity_change_type == "set":
        target_quantity = quantity_value

    elif quantity_change_type == "increase":
        target_quantity = current_quantity + quantity_value

    elif quantity_change_type == "decrease":
        target_quantity = current_quantity - quantity_value

    else:
        return {
            "result_type": "invalid_request",
            "reason": "unknown_quantity_change_type",
        }

    # 3. 목표 수량 검증

    # 현재 수량보다 더 많이 감소시킨 경우
    if target_quantity < 0:
        return {
            "result_type": "invalid_quantity",
            "reason": "target_quantity_below_zero",
            "current_quantity": current_quantity,
            "target_quantity": target_quantity,
        }

    # 수량 0은 변경으로 처리하지 않고 주문 취소 안내
    if target_quantity == 0:
        return {
            "result_type": "cancel_required",
            "reason": "target_quantity_zero",
            "current_quantity": current_quantity,
            "target_quantity": 0,
        }

    # 실제 수량 변화가 없는 경우
    if target_quantity == current_quantity:
        return {
            "result_type": "no_change",
            "reason": "same_quantity",
            "current_quantity": current_quantity,
            "target_quantity": target_quantity,
        }

    # 4. 변경 후 주문금액 계산

    new_total_price = unit_price * target_quantity
    price_difference = new_total_price - current_total_price

    # 5. 결제 차액 유형 판단

    if price_difference > 0:
        adjustment_type = "additional_payment_required"

    else:
        adjustment_type = "partial_refund_required"

    adjustment_amount = abs(price_difference)

    # 6. 계산 결과 반환

    return {
        "result_type": "change_preview",
        "current_quantity": current_quantity,
        "target_quantity": target_quantity,
        "unit_price": unit_price,
        "current_total_price": current_total_price,
        "new_total_price": new_total_price,
        "adjustment_type": adjustment_type,
        "adjustment_amount": adjustment_amount,
    }

# =========================================================
# 주문 수량 변경 가능 여부 확인 + 변경 내용 계산
# =========================================================

def check_order_change(
    orders: list[dict],
    payments: list[dict],
    customer_id: int,
    quantity_change_type: str | None,
    quantity_value: int | None,
    order_id: int | None = None,
) -> dict:
    """
    고객의 주문과 결제 정보를 조회한 뒤
    Order Change Policy를 적용하고,
    수량 정보가 충분하면 변경 예정 결과까지 계산한다.

    실제 주문 데이터는 수정하지 않는다.
    """

    # -----------------------------------------------------
    # 1. 해당 고객의 주문 조회
    # -----------------------------------------------------

    customer_orders = [
        order
        for order in orders
        if order["customer_id"] == customer_id
    ]

    if not customer_orders:
        return {
            "result_type": "not_found",
        }

    # -----------------------------------------------------
    # 2. 주문 식별
    # -----------------------------------------------------

    if order_id is not None:
        selected_order = next(
            (
                order
                for order in customer_orders
                if order["order_id"] == order_id
            ),
            None,
        )

        if selected_order is None:
            return {
                "result_type": "not_found",
            }

    else:
        # 주문이 여러 건이면 사용자 선택 필요
        if len(customer_orders) > 1:
            return {
                "result_type": "need_order_selection",
                "candidate_orders": [
                    {
                        "order_id": order["order_id"],
                        "order_date": order["order_date"],
                        "quantity": order["quantity"],
                        "total_price": order["total_price"],
                    }
                    for order in customer_orders
                ],
            }

        selected_order = customer_orders[0]

    # -----------------------------------------------------
    # 3. 결제 정보 조회
    # -----------------------------------------------------

    payment = next(
        (
            payment
            for payment in payments
            if payment["order_id"] == selected_order["order_id"]
        ),
        None,
    )

    if payment is None:
        return {
            "result_type": "payment_not_found",
            "order_id": selected_order["order_id"],
        }

    # -----------------------------------------------------
    # 4. Order Change Policy 적용
    # -----------------------------------------------------

    policy_result = judge_order_change(
        order_status=selected_order["order_status"],
        delivery_status=selected_order["delivery_status"],
        payment_status=payment["payment_status"],
    )

    # 변경 불가 또는 확인 필요 상태
    if policy_result["change_judgment"] != "changeable":
        return {
            "result_type": "not_changeable",
            "order_id": selected_order["order_id"],
            "order_status": selected_order["order_status"],
            "delivery_status": selected_order["delivery_status"],
            "payment_status": payment["payment_status"],
            "change_judgment": policy_result["change_judgment"],
            "reason": policy_result["reason"],
        }

    # -----------------------------------------------------
    # 5. 사용자가 수량을 아직 말하지 않은 경우
    # -----------------------------------------------------

    if quantity_change_type is None or quantity_value is None:
        return {
            "result_type": "need_quantity_input",
            "order_id": selected_order["order_id"],
            "current_quantity": selected_order["quantity"],
            "unit_price": selected_order["unit_price"],
            "current_total_price": selected_order["total_price"],
        }

    # -----------------------------------------------------
    # 6. 수량 변경 결과 계산
    # -----------------------------------------------------

    calculation_result = calculate_order_quantity_change(
        current_quantity=selected_order["quantity"],
        quantity_change_type=quantity_change_type,
        quantity_value=quantity_value,
        unit_price=selected_order["unit_price"],
        current_total_price=selected_order["total_price"],
    )

    # -----------------------------------------------------
    # 7. 주문 / 결제 정보와 계산 결과 반환
    # -----------------------------------------------------

    return {
        "result_type": calculation_result["result_type"],
        "order_id": selected_order["order_id"],
        "payment_id": payment["payment_id"],
        "order_status": selected_order["order_status"],
        "delivery_status": selected_order["delivery_status"],
        "payment_status": payment["payment_status"],
        "calculation": calculation_result,
    }


# =========================================================
# 주문 취소 순수 Action
# =========================================================

def cancel_order_action(
    orders: list[dict],
    payments: list[dict],
    customer_id: int,
    order_id: int,
) -> dict:
    """
    사용자의 최종 승인이 확인된 이후
    실제 주문과 결제 상태만 취소 처리한다.

    Refund 생성이나 환불 상태 관리는 수행하지 않는다.
    환불 처리는 Orchestrator가 Refund Service와 연결한다.
    """

    # -----------------------------------------------------
    # 1. 고객의 주문 확인
    # -----------------------------------------------------

    order = next(
        (
            order
            for order in orders
            if order["customer_id"] == customer_id
            and order["order_id"] == order_id
        ),
        None,
    )

    if order is None:
        return {
            "result_type": "action_failed",
            "reason": "order_not_found",
            "order_id": order_id,
        }

    # -----------------------------------------------------
    # 2. 결제 정보 확인
    # -----------------------------------------------------

    payment = next(
        (
            payment
            for payment in payments
            if payment["order_id"] == order_id
        ),
        None,
    )

    if payment is None:
        return {
            "result_type": "action_failed",
            "reason": "payment_not_found",
            "order_id": order_id,
        }

    # -----------------------------------------------------
    # 3. Action 직전 주문 취소 가능 여부 재검증
    # -----------------------------------------------------

    cancel_result = judge_order_cancel(
        order_status=order["order_status"],
        delivery_status=order["delivery_status"],
    )

    if cancel_result["cancel_judgment"] != "cancelable":
        return {
            "result_type": "action_failed",
            "reason": cancel_result["reason"],
            "order_id": order_id,
        }

    # -----------------------------------------------------
    # 4. Action 직전 결제 상태 재검증
    # -----------------------------------------------------

    if payment["payment_status"] != "payment_completed":
        return {
            "result_type": "action_failed",
            "reason": "invalid_payment_status",
            "order_id": order_id,
        }

    # -----------------------------------------------------
    # 5. 실제 주문 / 결제 취소
    # -----------------------------------------------------

    order["order_status"] = "order_canceled"
    payment["payment_status"] = "payment_canceled"

    # -----------------------------------------------------
    # 6. Action 결과 반환
    # -----------------------------------------------------

    return {
        "result_type": "success",
        "order_id": order_id,
        "order_status": order["order_status"],
        "payment_id": payment["payment_id"],
        "payment_method": payment["payment_method"],
        "payment_amount": payment["payment_amount"],
        "payment_status": payment["payment_status"],
    }

# =========================================================
# 배송지 변경 Action
# =========================================================

def change_delivery_address(
    orders: list[dict],
    customer_id: int,
    order_id: int,
    new_delivery_address: str,
) -> dict:
    """
    사용자의 최종 승인이 확인된 이후
    실제 주문의 배송지를 변경한다.

    이 함수는 Write Action이므로
    Orchestrator가 사용자 승인을 확인한 이후에만 호출해야 한다.
    """

    # -----------------------------------------------------
    # 1. 변경할 주소 기본 검증

    normalized_address = new_delivery_address.strip()

    if not normalized_address:
        return {
            "result_type": "action_failed",
            "reason": "invalid_delivery_address",
            "order_id": order_id,
        }

    # -----------------------------------------------------
    # 2. 해당 고객의 주문 확인

    order = next(
        (
            order
            for order in orders
            if order["customer_id"] == customer_id
            and order["order_id"] == order_id
        ),
        None,
    )

    if order is None:
        return {
            "result_type": "action_failed",
            "reason": "order_not_found",
            "order_id": order_id,
        }

    # -----------------------------------------------------
    # 3. Action 직전 배송지 변경 가능 여부 재확인

    address_change_result = judge_delivery_address_change(
        order_status=order["order_status"],
        delivery_status=order["delivery_status"],
    )

    if (
        address_change_result["address_change_judgment"]
        != "changeable"
    ):
        return {
            "result_type": "action_failed",
            "reason": address_change_result["reason"],
            "order_id": order_id,
        }

    # -----------------------------------------------------
    # 4. 기존 배송지 보관

    previous_delivery_address = order["delivery_address"]

    # -----------------------------------------------------
    # 5. 실제 배송지 변경

    order["delivery_address"] = normalized_address

    # -----------------------------------------------------
    # 6. Action 결과 반환

    return {
        "result_type": "success",
        "order_id": order_id,
        "previous_delivery_address": previous_delivery_address,
        "new_delivery_address": order["delivery_address"],
    }

# =========================================================
# 주문 수량 변경 Action
# =========================================================

def change_order_quantity(
    orders: list[dict],
    payments: list[dict],
    payment_adjustments: list[dict],
    customer_id: int,
    order_id: int,
    target_quantity: int,
) -> dict:
    """
    사용자의 최종 승인이 확인된 이후
    실제 주문 수량과 주문금액을 변경한다.

    실제 PG 추가결제 또는 부분환불은 수행하지 않고,
    필요한 결제 차액을 payment_adjustments에 pending 상태로 생성한다.
    """

    # -----------------------------------------------------
    # 1. 고객의 주문 확인
    # -----------------------------------------------------

    order = next(
        (
            order
            for order in orders
            if order["customer_id"] == customer_id
            and order["order_id"] == order_id
        ),
        None,
    )

    if order is None:
        return {
            "result_type": "action_failed",
            "reason": "order_not_found",
            "order_id": order_id,
        }

    # -----------------------------------------------------
    # 2. 결제 정보 확인
    # -----------------------------------------------------

    payment = next(
        (
            payment
            for payment in payments
            if payment["order_id"] == order_id
        ),
        None,
    )

    if payment is None:
        return {
            "result_type": "action_failed",
            "reason": "payment_not_found",
            "order_id": order_id,
        }

    # -----------------------------------------------------
    # 3. 기존 미처리 결제 차액 확인
    # -----------------------------------------------------

    pending_adjustment = next(
        (
            adjustment
            for adjustment in payment_adjustments
            if adjustment["order_id"] == order_id
            and adjustment["adjustment_status"] == "pending"
        ),
        None,
    )

    if pending_adjustment is not None:
        return {
            "result_type": "action_failed",
            "reason": "pending_payment_adjustment",
            "order_id": order_id,
        }

    # -----------------------------------------------------
    # 4. Action 직전 수량 변경 가능 여부 재확인
    # -----------------------------------------------------

    policy_result = judge_order_change(
        order_status=order["order_status"],
        delivery_status=order["delivery_status"],
        payment_status=payment["payment_status"],
    )

    if policy_result["change_judgment"] != "changeable":
        return {
            "result_type": "action_failed",
            "reason": policy_result["reason"],
            "order_id": order_id,
        }

    # -----------------------------------------------------
    # 5. Action 직전 현재 데이터 기준으로 다시 계산
    # -----------------------------------------------------

    calculation_result = calculate_order_quantity_change(
        current_quantity=order["quantity"],
        quantity_change_type="set",
        quantity_value=target_quantity,
        unit_price=order["unit_price"],
        current_total_price=order["total_price"],
    )

    if calculation_result["result_type"] != "change_preview":
        return {
            "result_type": "action_failed",
            "reason": calculation_result.get(
                "reason",
                calculation_result["result_type"],
            ),
            "order_id": order_id,
        }

    # 변경 전 값 보존
    previous_quantity = order["quantity"]
    previous_total_price = order["total_price"]

    # -----------------------------------------------------
    # 6. 주문 데이터 변경
    # -----------------------------------------------------

    order["quantity"] = calculation_result["target_quantity"]
    order["total_price"] = calculation_result["new_total_price"]

    # -----------------------------------------------------
    # 7. Payment Adjustment ID 생성
    # -----------------------------------------------------

    adjustment_id = (
        max(
            adjustment["adjustment_id"]
            for adjustment in payment_adjustments
        )
        + 1
        if payment_adjustments
        else 90001
    )

    # -----------------------------------------------------
    # 8. 결제 차액 데이터 생성
    # -----------------------------------------------------

    adjustment = {
        "adjustment_id": adjustment_id,
        "order_id": order_id,
        "payment_id": payment["payment_id"],
        "adjustment_type": calculation_result["adjustment_type"],
        "adjustment_amount": calculation_result["adjustment_amount"],
        "adjustment_status": "pending",
    }

    payment_adjustments.append(adjustment)

    # -----------------------------------------------------
    # 9. Action 결과 반환
    # -----------------------------------------------------

    return {
        "result_type": "success",
        "order_id": order_id,
        "payment_id": payment["payment_id"],
        "previous_quantity": previous_quantity,
        "new_quantity": order["quantity"],
        "previous_total_price": previous_total_price,
        "new_total_price": order["total_price"],
        "adjustment_id": adjustment_id,
        "adjustment_type": adjustment["adjustment_type"],
        "adjustment_amount": adjustment["adjustment_amount"],
        "adjustment_status": adjustment["adjustment_status"],
    }


# =========================================================
# 주문 확인 결과 → 사용자 응답 생성
# =========================================================

def generate_order_response(result: dict) -> str:

    result_type = result["result_type"]

    # 주문을 찾지 못한 경우
    if result_type == "not_found":
        return "확인되는 주문이 없습니다. 주문번호를 다시 확인해주세요."

    # 주문이 여러 개라 선택이 필요한 경우
    if result_type == "need_order_selection":

        candidate_orders = result["candidate_orders"]

        order_list = "\n".join(
            f"- 주문번호 {order['order_id']} / "
            f"{order['order_date']} / "
            f"{order['total_price']:,}원"
            for order in candidate_orders
        )

        return (
            "확인되는 주문이 여러 건 있습니다.\n"
            "확인할 주문을 선택해주세요.\n\n"
            f"{order_list}"
        )

    # 주문을 정상적으로 찾은 경우
    if result_type == "success":

        order_status = result["order_status"]
        order_id = result["order_id"]

        if order_status == "order_completed":
            return (
                f"주문번호 {order_id}의 주문은 "
                "정상적으로 완료되었습니다."
            )

        if order_status == "order_canceled":
            return (
                f"주문번호 {order_id}의 주문은 "
                "취소된 상태입니다."
            )

        if order_status == "order_failed":
            return (
                f"주문번호 {order_id}의 주문은 "
                "정상적으로 완료되지 않았습니다."
            )

    return "주문 상태를 확인하는 중 문제가 발생했습니다."


# =========================================================
# 결제 완료 확인
# =========================================================

def check_payment_completion(
    orders: list[dict],
    payments: list[dict],
    customer_id: int,
    order_id: int | None = None
) -> dict:

    # 해당 고객의 주문만 조회
    customer_orders = [
        order
        for order in orders
        if order["customer_id"] == customer_id
    ]

    # ---------------------------------------------------------
    # 사용자가 주문번호를 직접 입력한 경우
    if order_id is not None:

        selected_order = next(
            (
                order
                for order in customer_orders
                if order["order_id"] == order_id
            ),
            None
        )

        # 해당 고객의 주문이 아닌 경우
        if selected_order is None:
            return {
                "result_type": "not_found"
            }

        selected_order_id = order_id

    # ---------------------------------------------------------
    # 주문번호가 없는 경우
    else:

        # 고객의 주문 자체가 없는 경우
        if len(customer_orders) == 0:
            return {
                "result_type": "not_found"
            }

        # 주문이 여러 개라면 사용자가 선택해야 함
        if len(customer_orders) > 1:
            return {
                "result_type": "need_order_selection",
                "candidate_orders": [
                    {
                        "order_id": order["order_id"],
                        "order_date": order["order_date"],
                        "total_price": order["total_price"]
                    }
                    for order in customer_orders
                ]
            }

        # 주문이 하나라면 자동 선택
        selected_order_id = customer_orders[0]["order_id"]

    # ---------------------------------------------------------
    # 선택된 주문의 결제 데이터 조회
    payment = next(
        (
            payment
            for payment in payments
            if payment["order_id"] == selected_order_id
        ),
        None
    )

    # 결제 데이터가 없는 경우
    if payment is None:
        return {
            "result_type": "not_found"
        }

    # 결제 데이터 조회 성공
    return {
        "result_type": "success",
        "judgment": judge_payment_completion(payment["payment_status"]),
        "order_id": selected_order_id,
        "payment_id": payment["payment_id"],
        "payment_status": payment["payment_status"],
        "payment_method": payment["payment_method"],
        "payment_amount": payment["payment_amount"],
        "payment_date": payment["payment_date"]
    }


# =========================================================
# 결제 완료 확인 응답 생성
# =========================================================
def generate_payment_response(result: dict) -> str:

    result_type = result["result_type"]

    # ---------------------------------------------------------
    # 주문 또는 결제 정보를 찾지 못한 경우
   
    if result_type == "not_found":
        return "확인할 수 있는 주문 또는 결제 정보가 없습니다."

    # ---------------------------------------------------------
    # 주문이 여러 개라 사용자의 선택이 필요한 경우
    
    if result_type == "need_order_selection":

        candidate_orders = result["candidate_orders"]

        order_list = "\n".join(
            [
                f"- 주문번호 {order['order_id']} / "
                f"{order['order_date']} / "
                f"{order['total_price']:,}원"
                for order in candidate_orders
            ]
        )

        return (
            "확인되는 주문이 여러 건 있습니다.\n"
            "결제 여부를 확인할 주문을 선택해주세요.\n\n"
            f"{order_list}"
        )

    # ---------------------------------------------------------
    # 결제 데이터 조회 성공
    if result_type == "success":

        order_id = result["order_id"]
        payment_status = result["payment_status"]
        payment_method = result["payment_method"]
        payment_amount = result["payment_amount"]
        payment_date = result["payment_date"]

        if payment_status == "payment_completed":
            return (
                f"주문번호 {order_id}의 결제가 정상적으로 완료되었습니다.\n"
                f"결제금액: {payment_amount:,}원\n"
                f"결제수단: {payment_method}\n"
                f"결제일: {payment_date}"
            )

        if payment_status == "payment_failed":
            return (
                f"주문번호 {order_id}의 결제가 완료되지 않았습니다. "
                "결제 시도 중 실패한 것으로 확인됩니다."
            )

        if payment_status == "payment_canceled":
            return (
                f"주문번호 {order_id}의 결제는 취소된 상태입니다."
            )

    return "결제 상태를 확인할 수 없습니다."

def check_order_payment_consistency(
    orders: list[dict],
    payments: list[dict],
    customer_id: int,
    order_id: int,
) -> dict:
    """
    특정 주문의 주문 상태와 결제 상태가
    서로 일관된지 확인한다.
    """

    
    # 1. 해당 고객의 주문 확인

    order = next(
        (
            order
            for order in orders
            if order["customer_id"] == customer_id
            and order["order_id"] == order_id
        ),
        None,
    )

    if order is None:
        return {
            "result_type": "order_not_found",
            "consistency_judgment": "order_not_found",
            "order_id": order_id,
        }

    # 2. 해당 주문의 결제 정보 확인

    payment = next(
        (
            payment
            for payment in payments
            if payment["order_id"] == order_id
        ),
        None,
    )

    if payment is None:
        return {
            "result_type": "payment_not_found",
            "consistency_judgment": "payment_not_found",
            "order_id": order_id,
            "order_status": order["order_status"],
        }

    # 3. 주문-결제 상태 일관성 판정

    consistency_judgment = judge_order_payment_consistency(
        order_status=order["order_status"],
        payment_status=payment["payment_status"],
    )

    return {
        "result_type": "success",
        "consistency_judgment": consistency_judgment,
        "order_id": order_id,
        "order_status": order["order_status"],
        "payment_status": payment["payment_status"],
    }