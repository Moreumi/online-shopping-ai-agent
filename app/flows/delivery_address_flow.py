from app.services.order_payment_service import (
    check_delivery_address_change_eligibility,
    change_delivery_address,
)

from app.services.state_service import (
    reset_state,
    extract_order_id,
    extract_delivery_address,
    extract_confirmation,
)

# ----------------------------------------------------------#
# ----------------------------------------------------------#

def build_delivery_address_change_response(result: dict) -> str:

    result_type = result["result_type"]

    if result_type == "not_found":
        return (
            "배송지를 변경할 주문을 확인할 수 없습니다. "
            "주문번호를 다시 확인해 주세요."
        )

    if result_type == "need_order_selection":
        candidate_orders = result["candidate_orders"]

        order_list = "\n".join(
            f"- 주문번호 {order['order_id']} / "
            f"{order['order_date']} / "
            f"{order['total_price']:,}원 / "
            f"{order['delivery_address']}"
            for order in candidate_orders
        )

        return (
            "배송지를 변경할 주문을 선택해 주세요.\n\n"
            f"{order_list}"
        )

    if result_type != "success":
        return "배송지 변경 가능 여부를 확인하는 중 문제가 발생했습니다."

    judgment = result["address_change_judgment"]
    reason = result["reason"]

    if judgment == "changeable":
        return "변경할 새로운 배송지를 입력해 주세요."

    if (
        judgment == "not_changeable"
        and reason == "in_transit"
    ):
        return (
            "이미 배송이 시작된 주문은 "
            "배송지를 변경할 수 없습니다."
        )

    if (
        judgment == "not_changeable"
        and reason == "delivered"
    ):
        return (
            "이미 배송이 완료된 주문은 "
            "배송지를 변경할 수 없습니다."
        )

    if (
        judgment == "not_changeable"
        and reason == "order_canceled"
    ):
        return (
            "이미 취소된 주문은 "
            "배송지를 변경할 수 없습니다."
        )

    if (
        judgment == "not_changeable"
        and reason == "order_failed"
    ):
        return (
            "정상적으로 완료되지 않은 주문은 "
            "배송지를 변경할 수 없습니다."
        )

    return (
        "현재 주문 상태만으로 배송지 변경 가능 여부를 "
        "확인하기 어렵습니다. 추가 확인이 필요합니다."
    )


def start_delivery_address_flow(
    request,
    customer_id: int,
    orders: list[dict],
    state: dict,
) -> dict:
    result = check_delivery_address_change_eligibility(
        orders=orders,
        customer_id=customer_id,
        order_id=request.order_id,
    )

    if result["result_type"] == "need_order_selection":
        state["pending_action"] = "delivery_address_change_selection"
        state["candidate_orders"] = result["candidate_orders"]
        state["selected_order_id"] = None
        state["pending_data"] = {}

    elif (
        result["result_type"] == "success"
        and result["address_change_judgment"] == "changeable"
    ):
        state["pending_action"] = "collect_delivery_address"
        state["candidate_orders"] = []
        state["selected_order_id"] = result["order_id"]
        state["pending_data"] = {}

    response = build_delivery_address_change_response(result)

    return {
        "route": "delivery_address_change",
        "request": request.model_dump(),
        "result": result,
        "response": response,
    }

def handle_delivery_address_pending(
    user_input: str,
    customer_id: int,
    orders: list[dict],
    state: dict,
) -> dict | None:

    if state["pending_action"] == "delivery_address_change_selection":

        selected_order_id = extract_order_id(user_input)

        # 주문번호를 확인할 수 없는 경우
        if selected_order_id is None:
            return {
                "route": "delivery_address_change",
                "result": None,
                "response": (
                    "배송지를 변경할 주문번호를 입력해 주세요."
                ),
            }

        # 사용자가 선택할 수 있는 주문인지 확인
        candidate_order_ids = {
            order["order_id"]
            for order in state["candidate_orders"]
        }

        if selected_order_id not in candidate_order_ids:
            return {
                "route": "delivery_address_change",
                "result": None,
                "response": (
                    "선택 가능한 주문번호가 아닙니다. "
                    "안내된 주문번호 중에서 선택해 주세요."
                ),
            }

        # 선택한 주문의 배송지 변경 가능 여부 재확인
        result = check_delivery_address_change_eligibility(
            orders=orders,
            customer_id=customer_id,
            order_id=selected_order_id,
        )

        if (
            result["result_type"] == "success"
            and result["address_change_judgment"] == "changeable"
        ):
            state["pending_action"] = "collect_delivery_address"
            state["candidate_orders"] = []
            state["selected_order_id"] = selected_order_id
            state["pending_data"] = {}

        else:
            reset_state(state)

        response = build_delivery_address_change_response(result)

        return {
            "route": "delivery_address_change",
            "result": result,
            "response": response,
        }

    if state["pending_action"] == "collect_delivery_address":

        selected_order_id = state["selected_order_id"]

        # 어떤 주문의 배송지를 변경하는지 확인할 수 없는 경우
        if selected_order_id is None:
            reset_state(state)

            return {
                "route": "delivery_address_change",
                "result": {
                    "result_type": "action_failed",
                    "reason": "selected_order_not_found",
                },
                "response": (
                    "배송지를 변경할 주문 정보를 확인할 수 없습니다. "
                    "주문번호를 다시 입력해 주세요."
                ),
            }

        # 현재 고객의 해당 주문 확인
        selected_order = next(
            (
                order
                for order in orders
                if order["customer_id"] == customer_id
                and order["order_id"] == selected_order_id
            ),
            None,
        )

        if selected_order is None:
            reset_state(state)

            return {
                "route": "delivery_address_change",
                "result": {
                    "result_type": "action_failed",
                    "reason": "order_not_found",
                },
                "response": (
                    "배송지를 변경할 주문을 확인할 수 없습니다. "
                    "주문번호를 다시 확인해 주세요."
                ),
            }

        # 사용자가 입력한 새 배송지 추출
        new_delivery_address = extract_delivery_address(user_input)

        if new_delivery_address is None:
            return {
                "route": "delivery_address_change",
                "result": None,
                "response": "변경할 새로운 배송지를 입력해 주세요.",
            }

        # 실제 주문에는 아직 반영하지 않고 State에 저장
        state["pending_data"]["new_delivery_address"] = (
            new_delivery_address
        )

        state["pending_action"] = "confirm_delivery_address_change"

        current_delivery_address = selected_order["delivery_address"]

        return {
            "route": "delivery_address_change",
            "result": {
                "result_type": "confirmation_required",
                "order_id": selected_order_id,
                "current_delivery_address": current_delivery_address,
                "new_delivery_address": new_delivery_address,
            },
            "response": (
                f"현재 배송지: {current_delivery_address}\n"
                f"변경 배송지: {new_delivery_address}\n\n"
                "이 배송지로 변경하시겠어요? (예/아니오)"
            ),
        }
    if state["pending_action"] == "confirm_delivery_address_change":

        selected_order_id = state["selected_order_id"]

        new_delivery_address = state["pending_data"].get(
            "new_delivery_address"
        )

        # 어떤 주문인지 확인할 수 없는 경우
        if selected_order_id is None:
            reset_state(state)

            return {
                "route": "delivery_address_change",
                "result": {
                    "result_type": "action_failed",
                    "reason": "selected_order_not_found",
                },
                "response": (
                    "배송지를 변경할 주문 정보를 확인할 수 없습니다. "
                    "주문번호를 다시 입력해 주세요."
                ),
            }

        # 새 배송지 정보가 State에 없는 경우
        if new_delivery_address is None:
            reset_state(state)

            return {
                "route": "delivery_address_change",
                "result": {
                    "result_type": "action_failed",
                    "reason": "delivery_address_not_found",
                },
                "response": (
                    "변경할 배송지 정보를 확인할 수 없습니다. "
                    "배송지 변경을 다시 요청해 주세요."
                ),
            }

        confirmation = extract_confirmation(user_input)

        # 승인/거절이 불명확한 경우
        if confirmation is None:
            return {
                "route": "delivery_address_change",
                "result": None,
                "response": (
                    f"배송지를 '{new_delivery_address}'로 "
                    "변경하시려면 '예', 변경하지 않으시려면 "
                    "'아니오'라고 입력해 주세요."
                ),
            }

        # 사용자가 변경을 거절한 경우
        if confirmation is False:
            reset_state(state)

            return {
                "route": "delivery_address_change",
                "result": {
                    "result_type": "change_aborted",
                    "order_id": selected_order_id,
                },
                "response": "배송지 변경을 진행하지 않았습니다.",
            }

        # 사용자가 명확하게 승인한 경우에만 Write Action 실행
        result = change_delivery_address(
            orders=orders,
            customer_id=customer_id,
            order_id=selected_order_id,
            new_delivery_address=new_delivery_address,
        )

        if result["result_type"] == "success":
            reset_state(state)

            return {
                "route": "delivery_address_change",
                "result": result,
                "response": (
                    "배송지가 정상적으로 변경되었습니다.\n\n"
                    f"- 이전 배송지: "
                    f"{result['previous_delivery_address']}\n"
                    f"- 변경 배송지: "
                    f"{result['new_delivery_address']}"
                ),
            }

        reset_state(state)

        return {
            "route": "delivery_address_change",
            "result": result,
            "response": (
                "배송지 변경을 처리하지 못했습니다. "
                "현재 주문 상태를 다시 확인해 주세요."
            ),
        }    
    return None