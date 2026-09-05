from app.services.order_payment_service import (
    check_order_cancel_eligibility,
    cancel_order_action,
)

from app.services.refund_service import (
    validate_refund_request,
    start_refund,
)

from app.services.state_service import (
    extract_order_id,
    extract_confirmation,
    reset_state,
)

#----------------------------------------#


def build_order_cancel_pre_action_response(result: dict) -> str:

    result_type = result["result_type"]

    if result_type == "not_found":
        return (
            "취소할 주문을 확인할 수 없습니다. "
            "주문번호를 다시 확인해주세요."
        )

    if result_type == "need_order_selection":
        candidate_orders = result["candidate_orders"]

        order_list = "\n".join(
            f"- 주문번호 {order['order_id']} / "
            f"{order['order_date']} / "
            f"{order['total_price']:,}원"
            for order in candidate_orders
        )

        return (
            "취소 가능한 주문을 확인하기 위해 "
            "취소할 주문을 선택해주세요.\n\n"
            f"{order_list}"
        )

    if result_type != "success":
        return "주문 취소 가능 여부를 확인하는 중 문제가 발생했습니다."

    cancel_judgment = result["cancel_judgment"]
    reason = result["reason"]
    order_id = result["order_id"]

    if cancel_judgment == "cancelable":
        return (
            f"주문번호 {order_id}번 주문을 취소하시겠어요? "
            "(예/아니오)"
        )

    if cancel_judgment == "already_canceled":
        return "이미 정상적으로 주문이 취소되었습니다."

    if (
        cancel_judgment == "not_cancelable"
        and reason == "in_transit"
    ):
        return (
            "현재 배송 중인 주문은 취소가 어렵습니다. "
            "상품을 수령하신 후 취소를 원하시는 경우에는 "
            "교환/환불 카테고리로 문의해 주세요."
        )

    if (
        cancel_judgment == "not_cancelable"
        and reason == "delivered"
    ):
        return (
            "배송이 이미 완료되어 현재 주문 취소는 어렵습니다. "
            "배송 완료된 주문에 대해 취소를 원하시는 경우에는 "
            "교환/환불 카테고리로 문의해 주세요."
        )

    if (
        cancel_judgment == "not_cancelable"
        and reason == "order_failed"
    ):
        return (
            "정상적으로 완료되지 않은 주문으로 "
            "주문 취소를 진행할 수 없습니다."
        )

    return (
        "현재 주문 상태만으로 취소 가능 여부를 확인하기 어렵습니다. "
        "추가 확인이 필요합니다."
    )

def start_order_cancel_flow(
    request,
    customer_id: int,
    orders: list[dict],
    state: dict,
) -> dict:

    result = check_order_cancel_eligibility(
        orders=orders,
        customer_id=customer_id,
        order_id=request.order_id,
    )

    # 주문번호가 없고 주문이 여러 건인 경우
    if result["result_type"] == "need_order_selection":
        state["pending_action"] = "order_cancel_selection"
        state["candidate_orders"] = result["candidate_orders"]
        state["selected_order_id"] = None

    # 주문이 특정되었고 취소 가능한 경우
    elif (
        result["result_type"] == "success"
        and result["cancel_judgment"] == "cancelable"
    ):
        state["pending_action"] = "confirm_cancel"
        state["candidate_orders"] = []
        state["selected_order_id"] = result["order_id"]

    response = build_order_cancel_pre_action_response(result)

    return {
        "route": "order_cancel",
        "request": request.model_dump(),
        "result": result,
        "response": response,
    }


def handle_order_cancel_pending(
    user_input: str,
    customer_id: int,
    orders: list[dict],
    state: dict,
    payments: list[dict] | None = None,
    refunds: list[dict] | None = None,
) -> dict | None:

    if state["pending_action"] == "order_cancel_selection":

        selected_order_id = extract_order_id(user_input)

        # 주문번호를 확인할 수 없는 경우
        if selected_order_id is None:
            return {
                "route": "order_cancel",
                "result": None,
                "response": "취소할 주문번호를 입력해 주세요.",
            }

        # 안내된 후보 주문 중 하나인지 확인
        candidate_order_ids = {
            order["order_id"]
            for order in state["candidate_orders"]
        }

        if selected_order_id not in candidate_order_ids:
            return {
                "route": "order_cancel",
                "result": None,
                "response": (
                    "선택 가능한 주문번호가 아닙니다. "
                    "안내된 주문번호 중에서 선택해 주세요."
                ),
            }

        # 선택한 주문의 취소 가능 여부 재확인
        result = check_order_cancel_eligibility(
            orders=orders,
            customer_id=customer_id,
            order_id=selected_order_id,
        )

        if (
            result["result_type"] == "success"
            and result["cancel_judgment"] == "cancelable"
        ):
            state["pending_action"] = "confirm_cancel"
            state["candidate_orders"] = []
            state["selected_order_id"] = selected_order_id

        else:
            reset_state(state)

        response = build_order_cancel_pre_action_response(result)

        return {
            "route": "order_cancel",
            "result": result,
            "response": response,
        }
    
    if state["pending_action"] == "confirm_cancel":

        selected_order_id = state["selected_order_id"]

        # 어떤 주문을 취소하는지 확인할 수 없는 경우
        if selected_order_id is None:
            reset_state(state)

            return {
                "route": "order_cancel",
                "result": {
                    "result_type": "action_failed",
                    "reason": "selected_order_not_found",
                },
                "response": (
                    "취소할 주문 정보를 확인할 수 없습니다. "
                    "주문번호를 다시 입력해 주세요."
                ),
            }

        confirmation = extract_confirmation(user_input)

        # 승인/거절이 불명확한 경우
        if confirmation is None:
            return {
                "route": "order_cancel",
                "result": None,
                "response": (
                    f"주문번호 {selected_order_id}번 주문 취소를 "
                    "진행하시려면 '예', 취소하지 않으시려면 "
                    "'아니오'라고 입력해 주세요."
                ),
            }

        # 사용자가 취소를 거절한 경우
        if confirmation is False:
            reset_state(state)

            return {
                "route": "order_cancel",
                "result": {
                    "result_type": "cancel_aborted",
                    "order_id": selected_order_id,
                },
                "response": "주문 취소를 진행하지 않았습니다.",
            }

        if payments is None:
            payments = []

        if refunds is None:
            refunds = []

        # 실제 주문/결제를 변경하기 전에 Refund 가능 여부 검증
        refund_validation = validate_refund_request(
            payments=payments,
            order_id=selected_order_id,
            refund_type="full",
            refund_amount=None,
        )

        if refund_validation["result_type"] != "success":
            reset_state(state)

            return {
                "route": "order_cancel",
                "result": refund_validation,
                "response": (
                    "주문 취소에 필요한 환불 정보를 확인하지 못했습니다. "
                    "현재 결제 상태를 다시 확인해 주세요."
                ),
            }

        # 주문 / 결제 취소
        cancel_result = cancel_order_action(
            orders=orders,
            payments=payments,
            customer_id=customer_id,
            order_id=selected_order_id,
        )

        if cancel_result["result_type"] != "success":
            reset_state(state)

            return {
                "route": "order_cancel",
                "result": cancel_result,
                "response": build_order_cancel_action_response(
                    cancel_result
                ),
            }

        # Refund Service 연결
        refund_result = start_refund(
            payments=payments,
            refunds=refunds,
            order_id=selected_order_id,
            refund_amount=None,
            refund_type="full",
            refund_reason="order_cancel",
        )

        # 주문/결제 취소는 성공했지만 Refund 시작 실패
        if refund_result["result_type"] == "action_failed":
            reset_state(state)

            return {
                "route": "order_cancel",
                "result": {
                    "order_cancel": cancel_result,
                    "refund": refund_result,
                },
                "response": (
                    "주문과 결제는 취소되었지만 "
                    "환불 절차를 시작하는 중 문제가 발생했습니다. "
                    "환불 상태를 추가로 확인해 주세요."
                ),
            }

        # 기존 외부 Interface 유지
        result = {
            **cancel_result,
            **refund_result,
        }

        response = build_order_cancel_action_response(result)

        # 계좌이체라 환불계좌가 필요한 경우
        if result["result_type"] == "refund_account_required":
            state["pending_action"] = "collect_refund_account"
            state["candidate_orders"] = []
            state["selected_order_id"] = selected_order_id
            state["pending_data"] = {
                "refund_id": result["refund_id"],
                "refund_amount": result["refund_amount"],
                "refund_type": "full",
                "source": "order_cancel",
            }

        else:
            reset_state(state)

        return {
            "route": "order_cancel",
            "result": result,
            "response": response,
        }
    return None

def build_order_cancel_action_response(result: dict) -> str:
    """
    실제 주문 취소 Action 실행 후 결과에 따라
    사용자에게 안내할 응답을 생성한다.
    """

    result_type = result["result_type"]

    # 카드 결제 취소
    if (
        result_type == "success"
        and result.get("payment_method") == "card"
    ):
        return (
            "주문이 정상적으로 취소되었습니다. "
            "카드 결제 취소는 카드사를 통해 처리되며, "
            "환불 완료까지 영업일 기준 7일 정도 소요될 수 있습니다."
        )

    # 계좌이체 결제 취소
    if result_type == "refund_account_required":
        return (
            "주문이 정상적으로 취소되었습니다. "
            "환불을 위해 환불받으실 계좌 정보를 입력해 주세요."
        )

    # Action 실패
    if result_type == "action_failed":
        return (
            "주문 취소 처리 중 문제가 발생했습니다. "
            "현재 주문 상태를 다시 확인해 주세요."
        )

    return "주문 취소 처리 결과를 확인하는 중 문제가 발생했습니다."