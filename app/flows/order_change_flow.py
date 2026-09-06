from app.services.order_payment_service import (
    check_order_change,
    change_order_quantity,
)

from app.services.refund_service import (
    start_refund,
)

from app.services.state_service import (
    extract_order_id,
    extract_quantity_change_request,
    extract_confirmation,
    reset_state,
)

# =========================================================
# 주문 수량 변경 Preview 결과 → 사용자 응답
# =========================================================

def build_order_change_response(result: dict) -> str:
    """
    주문 수량 변경 가능 여부 및 계산 결과를
    사용자 안내 문장으로 변환한다.

    실제 Write Action은 수행하지 않는다.
    """

    result_type = result["result_type"]

    # -----------------------------------------------------
    # 주문 조회 실패
    # -----------------------------------------------------

    if result_type == "not_found":
        return (
            "수량을 변경할 주문을 확인할 수 없습니다. "
            "주문번호를 다시 확인해 주세요."
        )

    # -----------------------------------------------------
    # 여러 주문 중 선택 필요
    # -----------------------------------------------------

    if result_type == "need_order_selection":
        candidate_orders = result["candidate_orders"]

        order_list = "\n".join(
            f"- 주문번호 {order['order_id']} / "
            f"{order['order_date']} / "
            f"현재 수량 {order['quantity']}개 / "
            f"{order['total_price']:,}원"
            for order in candidate_orders
        )

        return (
            "수량을 변경할 주문을 선택해 주세요.\n\n"
            f"{order_list}"
        )

    # -----------------------------------------------------
    # 결제 정보 없음
    # -----------------------------------------------------

    if result_type == "payment_not_found":
        return (
            "해당 주문의 결제 정보를 확인할 수 없어 "
            "수량 변경을 진행할 수 없습니다."
        )

    # -----------------------------------------------------
    # 변경 불가
    # -----------------------------------------------------

    if result_type == "not_changeable":
        reason = result.get("reason")

        if reason == "order_canceled":
            return "이미 취소된 주문은 수량을 변경할 수 없습니다."

        if reason == "order_failed":
            return (
                "정상적으로 완료되지 않은 주문은 "
                "수량을 변경할 수 없습니다."
            )

        if reason == "in_transit":
            return (
                "이미 배송이 시작된 주문은 "
                "수량을 변경할 수 없습니다."
            )

        if reason == "delivered":
            return (
                "이미 배송이 완료된 주문은 "
                "수량을 변경할 수 없습니다."
            )

        if reason == "payment_failed":
            return (
                "결제가 정상적으로 완료되지 않은 주문은 "
                "수량을 변경할 수 없습니다."
            )

        if reason == "payment_canceled":
            return (
                "결제가 취소된 주문은 "
                "수량을 변경할 수 없습니다."
            )

        return (
            "현재 주문 상태에서는 수량 변경을 진행하기 어렵습니다."
        )

    # 수량 정보 추가 입력 필요

    if result_type == "need_quantity_input":
        current_quantity = result["current_quantity"]

        return (
            f"현재 주문 수량은 {current_quantity}개입니다. "
            "변경할 수량을 말씀해 주세요. "
            "예: '3개로 변경', '1개 추가', '1개 줄여줘'"
        )

    # 수량 0 → 주문 취소 필요

    if result_type == "cancel_required":
        return (
            "수량을 0개로 변경할 수는 없습니다. "
            "해당 주문을 없애려면 주문 취소가 필요합니다. "
            "원하시면 주문 취소를 요청해 주세요."
        )

    # 잘못된 수량

    if result_type == "invalid_quantity":
        return (
            "변경 후 수량이 0개보다 작아질 수 없습니다. "
            "변경할 수량을 다시 입력해 주세요."
        )

    # 현재와 동일한 수량

    if result_type == "no_change":
        return "현재 주문 수량과 동일하여 변경할 내용이 없습니다."

    # 주문 데이터 불일치

    if result_type == "data_inconsistent":
        return (
            "현재 주문의 수량과 주문금액 정보가 일치하지 않아 "
            "수량 변경을 진행할 수 없습니다."
        )

    # 정상 Preview → 최종 승인 요청

    if result_type == "change_preview":
        calculation = result["calculation"]

        current_quantity = calculation["current_quantity"]
        target_quantity = calculation["target_quantity"]

        current_total_price = calculation["current_total_price"]
        new_total_price = calculation["new_total_price"]

        adjustment_type = calculation["adjustment_type"]
        adjustment_amount = calculation["adjustment_amount"]

        if adjustment_type == "additional_payment_required":
            adjustment_message = (
                f"추가 결제 필요 금액: {adjustment_amount:,}원"
            )

        else:
            adjustment_message = (
                f"부분 환불 예정 금액: {adjustment_amount:,}원"
            )

        return (
            f"주문번호 {result['order_id']}번의 수량을 "
            f"{current_quantity}개에서 {target_quantity}개로 변경합니다.\n\n"
            f"- 현재 주문금액: {current_total_price:,}원\n"
            f"- 변경 후 주문금액: {new_total_price:,}원\n"
            f"- {adjustment_message}\n\n"
            "이대로 변경하시겠어요? (예/아니오)"
        )

    return (
        "주문 수량 변경 내용을 확인하는 중 문제가 발생했습니다."
    )
def start_order_change_flow(
    request,
    customer_id: int,
    orders: list[dict],
    state: dict,
    payments: list[dict] | None = None,
) -> dict:

    if payments is None:
        payments = []

    result = check_order_change(
        orders=orders,
        payments=payments,
        customer_id=customer_id,
        quantity_change_type=request.quantity_change_type,
        quantity_value=request.quantity_value,
        order_id=request.order_id,
    )

    # 1. 주문이 여러 건 → 주문 선택
    if result["result_type"] == "need_order_selection":
        state["pending_action"] = "order_change_selection"
        state["candidate_orders"] = result["candidate_orders"]
        state["selected_order_id"] = None
        state["pending_data"] = {
            "quantity_change_type": request.quantity_change_type,
            "quantity_value": request.quantity_value,
        }

    # 2. 주문은 정해졌지만 수량 정보 부족
    elif result["result_type"] == "need_quantity_input":
        state["pending_action"] = "order_change_quantity_input"
        state["candidate_orders"] = []
        state["selected_order_id"] = result["order_id"]
        state["pending_data"] = {}

    # 3. 정상 Preview → 최종 승인 대기
    elif result["result_type"] == "change_preview":
        calculation = result["calculation"]

        state["pending_action"] = "order_change_confirmation"
        state["candidate_orders"] = []
        state["selected_order_id"] = result["order_id"]

        state["pending_data"] = {
            "target_quantity": calculation["target_quantity"],
            "current_quantity": calculation["current_quantity"],
            "current_total_price": calculation["current_total_price"],
            "new_total_price": calculation["new_total_price"],
            "adjustment_type": calculation["adjustment_type"],
            "adjustment_amount": calculation["adjustment_amount"],
        }

    else:
        reset_state(state)

    response = build_order_change_response(result)

    return {
        "route": "order_change",
        "request": request.model_dump(),
        "result": result,
        "response": response,
    }


def handle_order_change_pending(
    user_input: str,
    customer_id: int,
    orders: list[dict],
    state: dict,
    payments: list[dict] | None = None,
    refunds: list[dict] | None = None,
    payment_adjustments: list[dict] | None = None,
) -> dict | None:

    # -----------------------------------------------------
    # 주문 수량 변경 - 주문 선택
    # -----------------------------------------------------

    if state["pending_action"] == "order_change_selection":

        # -------------------------------------------------
        # 1. 사용자 입력에서 주문번호 추출
        # -------------------------------------------------

        selected_order_id = extract_order_id(user_input)

        if selected_order_id is None:
            return {
                "route": "order_change",
                "result": None,
                "response": (
                    "수량을 변경할 주문번호를 입력해 주세요."
                ),
            }

        # -------------------------------------------------
        # 2. 안내했던 후보 주문인지 확인
        # -------------------------------------------------

        candidate_order_ids = {
            order["order_id"]
            for order in state["candidate_orders"]
        }

        if selected_order_id not in candidate_order_ids:
            return {
                "route": "order_change",
                "result": None,
                "response": (
                    "선택 가능한 주문번호가 아닙니다. "
                    "안내된 주문번호 중에서 선택해 주세요."
                ),
            }

        # -------------------------------------------------
        # 3. 첫 번째 턴에서 저장했던 수량 변경 요청 복구
        # -------------------------------------------------

        quantity_change_type = state["pending_data"].get(
            "quantity_change_type"
        )

        quantity_value = state["pending_data"].get(
            "quantity_value"
        )

        if payments is None:
            payments = []

        # -------------------------------------------------
        # 4. 선택한 주문을 기준으로 다시 Policy + 계산
        # -------------------------------------------------

        result = check_order_change(
            orders=orders,
            payments=payments,
            customer_id=customer_id,
            quantity_change_type=quantity_change_type,
            quantity_value=quantity_value,
            order_id=selected_order_id,
        )

        # -------------------------------------------------
        # 5-1. 처음부터 수량을 말하지 않았던 경우
        #      → 이제 수량 입력 요청
        # -------------------------------------------------

        if result["result_type"] == "need_quantity_input":

            state["pending_action"] = "order_change_quantity_input"
            state["candidate_orders"] = []
            state["selected_order_id"] = selected_order_id
            state["pending_data"] = {}

        # -------------------------------------------------
        # 5-2. 수량 정보까지 이미 있었다면
        #      → Preview 완료, 최종 승인 단계
        # -------------------------------------------------

        elif result["result_type"] == "change_preview":

            calculation = result["calculation"]

            state["pending_action"] = "order_change_confirmation"
            state["candidate_orders"] = []
            state["selected_order_id"] = selected_order_id

            state["pending_data"] = {
                "target_quantity": calculation["target_quantity"],
                "current_quantity": calculation["current_quantity"],
                "current_total_price": calculation[
                    "current_total_price"
                ],
                "new_total_price": calculation["new_total_price"],
                "adjustment_type": calculation["adjustment_type"],
                "adjustment_amount": calculation["adjustment_amount"],
            }

        # -------------------------------------------------
        # 5-3. 배송중 / 수량 0 / 오류 등
        #      → 흐름 종료
        # -------------------------------------------------

        else:
            reset_state(state)

        response = build_order_change_response(result)

        return {
            "route": "order_change",
            "result": result,
            "response": response,
        }
    # -----------------------------------------------------
    # 주문 수량 변경 - 수량 입력
    # -----------------------------------------------------

    if state["pending_action"] == "order_change_quantity_input":

        selected_order_id = state["selected_order_id"]

        # -------------------------------------------------
        # 1. 어떤 주문인지 확인
        # -------------------------------------------------

        if selected_order_id is None:
            reset_state(state)

            return {
                "route": "order_change",
                "result": {
                    "result_type": "action_failed",
                    "reason": "selected_order_not_found",
                },
                "response": (
                    "수량을 변경할 주문 정보를 확인할 수 없습니다. "
                    "주문 수량 변경을 다시 요청해 주세요."
                ),
            }

        # -------------------------------------------------
        # 2. 사용자의 수량 변경 입력 추출
        # -------------------------------------------------

        quantity_request = extract_quantity_change_request(
            user_input
        )

        if quantity_request is None:
            return {
                "route": "order_change",
                "result": None,
                "response": (
                    "변경할 수량을 다시 입력해 주세요. "
                    "예: '3개로 변경', '1개 추가', '1개 줄여줘'"
                ),
            }

        quantity_change_type = quantity_request[
            "quantity_change_type"
        ]

        quantity_value = quantity_request[
            "quantity_value"
        ]

        if payments is None:
            payments = []

        # -------------------------------------------------
        # 3. 실제 주문 데이터 기준으로 Policy + 계산
        # -------------------------------------------------

        result = check_order_change(
            orders=orders,
            payments=payments,
            customer_id=customer_id,
            quantity_change_type=quantity_change_type,
            quantity_value=quantity_value,
            order_id=selected_order_id,
        )

        # -------------------------------------------------
        # 4. 정상 Preview
        #    → 최종 승인 단계로 이동
        # -------------------------------------------------

        if result["result_type"] == "change_preview":

            calculation = result["calculation"]

            state["pending_action"] = "order_change_confirmation"
            state["candidate_orders"] = []
            state["selected_order_id"] = selected_order_id

            state["pending_data"] = {
                "target_quantity": calculation["target_quantity"],
                "current_quantity": calculation["current_quantity"],
                "current_total_price": calculation[
                    "current_total_price"
                ],
                "new_total_price": calculation["new_total_price"],
                "adjustment_type": calculation["adjustment_type"],
                "adjustment_amount": calculation["adjustment_amount"],
            }

        # -------------------------------------------------
        # 5. 잘못된 수량 / 현재와 동일한 수량
        #    → 같은 주문에 대해 다시 입력받음
        # -------------------------------------------------

        elif result["result_type"] in {
            "invalid_quantity",
            "no_change",
        }:
            state["pending_action"] = "order_change_quantity_input"
            state["candidate_orders"] = []
            state["selected_order_id"] = selected_order_id
            state["pending_data"] = {}

        # -------------------------------------------------
        # 6. 취소 필요 / 변경 불가 / 데이터 오류
        #    → 현재 order_change 흐름 종료
        # -------------------------------------------------

        else:
            reset_state(state)

        response = build_order_change_response(result)

        return {
            "route": "order_change",
            "result": result,
            "response": response,
        }
# -----------------------------------------------------
    # 주문 수량 변경 - 최종 승인
    # -----------------------------------------------------

    if state["pending_action"] == "order_change_confirmation":

        selected_order_id = state["selected_order_id"]

        target_quantity = state["pending_data"].get(
            "target_quantity"
        )

        # 1. State 정보 확인

        if selected_order_id is None:
            reset_state(state)

            return {
                "route": "order_change",
                "result": {
                    "result_type": "action_failed",
                    "reason": "selected_order_not_found",
                },
                "response": (
                    "수량을 변경할 주문 정보를 확인할 수 없습니다. "
                    "주문 수량 변경을 다시 요청해 주세요."
                ),
            }

        if target_quantity is None:
            reset_state(state)

            return {
                "route": "order_change",
                "result": {
                    "result_type": "action_failed",
                    "reason": "target_quantity_not_found",
                    "order_id": selected_order_id,
                },
                "response": (
                    "변경할 수량 정보를 확인할 수 없습니다. "
                    "주문 수량 변경을 다시 요청해 주세요."
                ),
            }

        # 2. 사용자 최종 승인 여부 확인

        confirmation = extract_confirmation(user_input)

        # 예 / 아니오가 불명확
        if confirmation is None:
            return {
                "route": "order_change",
                "result": None,
                "response": (
                    f"주문번호 {selected_order_id}번의 수량을 "
                    f"{target_quantity}개로 변경하시려면 '예', "
                    "변경하지 않으시려면 '아니오'라고 입력해 주세요."
                ),
            }

        # 3. 사용자가 변경을 거절

        if confirmation is False:
            reset_state(state)

            return {
                "route": "order_change",
                "result": {
                    "result_type": "change_aborted",
                    "order_id": selected_order_id,
                },
                "response": "주문 수량 변경을 진행하지 않았습니다.",
            }

        # 4. 사용자가 명확하게 승인
        #    여기에서만 실제 Write Action 실행

        if payments is None:
            payments = []

        if payment_adjustments is None:
            payment_adjustments = []

        result = change_order_quantity(
            orders=orders,
            payments=payments,
            payment_adjustments=payment_adjustments,
            customer_id=customer_id,
            order_id=selected_order_id,
            target_quantity=target_quantity,
        )

        # 5. Action 성공

        if result["result_type"] == "success":

            adjustment_type = result["adjustment_type"]

            # -------------------------------------------------
            # 수량 증가 → 추가 결제 필요
            # -------------------------------------------------

            if adjustment_type == "additional_payment_required":

                reset_state(state)

                adjustment_message = (
                    f"추가 결제 필요 금액은 "
                    f"{result['adjustment_amount']:,}원이며, "
                    "현재 추가 결제 처리는 대기 상태입니다."
                )

                return {
                    "route": "order_change",
                    "result": result,
                    "response": (
                        "주문 수량이 정상적으로 변경되었습니다.\n\n"
                        f"- 이전 수량: {result['previous_quantity']}개\n"
                        f"- 변경 수량: {result['new_quantity']}개\n"
                        f"- 이전 주문금액: "
                        f"{result['previous_total_price']:,}원\n"
                        f"- 변경 주문금액: "
                        f"{result['new_total_price']:,}원\n\n"
                        f"{adjustment_message}"
                    ),
                }

            # -------------------------------------------------
            # 수량 감소 → 부분 환불 Flow 연결
            # -------------------------------------------------

            if adjustment_type == "partial_refund_required":

                if refunds is None:
                    refunds = []

                refund_result = start_refund(
                    payments=payments,
                    refunds=refunds,
                    order_id=selected_order_id,
                    refund_amount=result["adjustment_amount"],
                    refund_type="partial",
                    refund_reason="order_quantity_decrease",
                    adjustment_id=result.get("adjustment_id"),
                )

                # ---------------------------------------------
                # 카드 → 부분 환불 처리 시작
                # ---------------------------------------------

                if refund_result["result_type"] == "success":

                    reset_state(state)

                    return {
                        "route": "order_change",
                        "result": {
                            "order_change": result,
                            "refund": refund_result,
                        },
                        "response": (
                            "주문 수량이 정상적으로 변경되었습니다.\n\n"
                            f"- 이전 수량: "
                            f"{result['previous_quantity']}개\n"
                            f"- 변경 수량: "
                            f"{result['new_quantity']}개\n"
                            f"- 이전 주문금액: "
                            f"{result['previous_total_price']:,}원\n"
                            f"- 변경 주문금액: "
                            f"{result['new_total_price']:,}원\n\n"
                            f"차액 "
                            f"{refund_result['refund_amount']:,}원에 대한 "
                            "카드 부분 환불 절차를 시작했습니다. "
                            "현재 환불 처리 중입니다."
                        ),
                    }

                # ---------------------------------------------
                # 계좌이체 → 환불계좌 입력 필요
                # ---------------------------------------------

                if (
                    refund_result["result_type"]
                    == "refund_account_required"
                ):

                    state["pending_action"] = "collect_refund_account"
                    state["candidate_orders"] = []
                    state["selected_order_id"] = selected_order_id
                    state["pending_data"] = {
                        "refund_id": refund_result["refund_id"],
                        "refund_amount": refund_result[
                            "refund_amount"
                        ],
                        "refund_type": "partial",
                        "source": "order_change",
                    }

                    return {
                        "route": "order_change",
                        "result": {
                            "order_change": result,
                            "refund": refund_result,
                        },
                        "response": (
                            "주문 수량이 정상적으로 변경되었습니다.\n\n"
                            f"- 이전 수량: "
                            f"{result['previous_quantity']}개\n"
                            f"- 변경 수량: "
                            f"{result['new_quantity']}개\n"
                            f"- 이전 주문금액: "
                            f"{result['previous_total_price']:,}원\n"
                            f"- 변경 주문금액: "
                            f"{result['new_total_price']:,}원\n\n"
                            f"차액 "
                            f"{refund_result['refund_amount']:,}원의 "
                            "부분 환불이 필요합니다. "
                            "환불받으실 계좌 정보를 입력해 주세요.\n"
                            "예: 국민은행 / 1234567890 / 홍길동"
                        ),
                    }

                # ---------------------------------------------
                # Refund Flow 시작 실패
                # ---------------------------------------------

                reset_state(state)

                return {
                    "route": "order_change",
                    "result": {
                        "order_change": result,
                        "refund": refund_result,
                    },
                    "response": (
                        "주문 수량은 정상적으로 변경되었지만, "
                        "부분 환불 절차를 시작하는 중 문제가 발생했습니다. "
                        "환불 상태를 추가로 확인해 주세요."
                    ),
                }
        # 6. Action 실패

        reset_state(state)

        reason = result.get("reason")

        if reason == "in_transit":
            response = (
                "확인하는 사이 배송이 시작되어 "
                "주문 수량을 변경할 수 없습니다."
            )

        elif reason == "delivered":
            response = (
                "현재 배송이 완료된 상태라 "
                "주문 수량을 변경할 수 없습니다."
            )

        elif reason == "payment_failed":
            response = (
                "현재 결제 상태가 정상적이지 않아 "
                "주문 수량을 변경할 수 없습니다."
            )

        elif reason == "pending_payment_adjustment":
            response = (
                "이 주문에는 아직 처리되지 않은 결제 차액이 있어 "
                "추가 수량 변경을 진행할 수 없습니다."
            )

        else:
            response = (
                "주문 수량 변경을 처리하지 못했습니다. "
                "현재 주문 상태를 다시 확인해 주세요."
            )

        return {
            "route": "order_change",
            "result": result,
            "response": response,
        }
    
    return None
    