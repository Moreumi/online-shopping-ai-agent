from app.services.llm_service import classification_chain

from app.services.order_payment_service import (
    check_order_completion,
    generate_order_response,
    check_payment_completion,
    generate_payment_response,
    check_order_payment_consistency,
)

from app.policies.order_payment_consistency_policy import (
    ORDER_PAYMENT_CONSISTENCY_POLICY_CONTEXT,
)

from app.services.state_service import (
    reset_state,
    extract_order_id,
    extract_refund_account,
)

from app.services.response_service import generate_cs_response

from app.policies.order_completion_policy import (
    ORDER_COMPLETION_POLICY_CONTEXT,
)

from app.policies.payment_completion_policy import (
    PAYMENT_COMPLETION_POLICY_CONTEXT,
)

from app.policies.payment_method_change_policy import (
    judge_payment_method_change,
)

from app.services.delivery_service import check_delivery_status

from app.policies.delivery_eta_policy import (
    get_general_delivery_eta_policy,
    judge_order_delivery_eta,
)

from app.services.refund_service import (
    register_refund_account as register_refund_account_common,
)

from app.flows.delivery_address_flow import (
    start_delivery_address_flow,
)

from app.flows.delivery_address_flow import (
    start_delivery_address_flow,
    handle_delivery_address_pending,
)

from app.flows.order_cancel_flow import (
    start_order_cancel_flow,
)

from app.flows.order_cancel_flow import (
    start_order_cancel_flow,
    handle_order_cancel_pending,
)

from app.flows.order_change_flow import (
    start_order_change_flow,
    handle_order_change_pending,
)


# =========================================================
# 1. 주문 완료 확인 최종 응답 생성
# =========================================================

def build_order_confirmation_response(
    user_input: str,
    result: dict,
    consistency_result: dict | None = None,
) -> str:
    """
    주문 완료 확인 결과와 주문-결제 일관성 결과에 따라
    최종 응답 생성 방식을 결정한다.

    - 주문 조회 실패 / 선택 필요:
      기존 Python 응답 사용

    - 주문 조회 성공 + 일관성 문제 없음:
      fact_summary 사용

    - 주문 조회 성공 + 주문/결제 불일치:
      narrative_guidance 사용
    """

    if result.get("result_type") != "success":
        return generate_order_response(result)

    # 주문-결제 상태가 비정상적이거나
    # 결제 정보를 확인할 수 없는 경우
    if consistency_result is not None:
        consistency_judgment = consistency_result.get(
            "consistency_judgment"
        )

        if consistency_judgment in {
            "needs_review",
            "payment_not_found",
            "order_not_found",
        }:
            combined_result = {
                "order_result": result,
                "consistency_result": consistency_result,
            }

            return generate_cs_response(
                user_input=user_input,
                sub_intent="order_confirmation",
                response_mode="narrative_guidance",
                result=combined_result,
                policy_context=(
                    ORDER_COMPLETION_POLICY_CONTEXT
                    + "\n\n"
                    + ORDER_PAYMENT_CONSISTENCY_POLICY_CONTEXT
                ),
            )

    # 정상적인 조회 결과
    return generate_cs_response(
        user_input=user_input,
        sub_intent="order_confirmation",
        response_mode="fact_summary",
        result=result,
        policy_context=ORDER_COMPLETION_POLICY_CONTEXT,
    )


# =========================================================
# 2. 결제 완료 확인 최종 응답 생성
# =========================================================

def build_payment_confirmation_response(
    user_input: str,
    result: dict,
    consistency_result: dict | None = None,
) -> str:
    """
    결제 완료 확인 결과와 주문-결제 일관성 결과에 따라
    최종 응답 생성 방식을 결정한다.

    - 결제 조회 실패 / 선택 필요:
      기존 Python 응답 사용

    - 결제 조회 성공 + 일관성 문제 없음:
      fact_summary 사용

    - 결제 조회 성공 + 주문/결제 불일치:
      narrative_guidance 사용
    """

    if result.get("result_type") != "success":
        return generate_payment_response(result)

    if consistency_result is not None:
        consistency_judgment = consistency_result.get(
            "consistency_judgment"
        )

        if consistency_judgment in {
            "needs_review",
            "payment_not_found",
            "order_not_found",
        }:
            combined_result = {
                "payment_result": result,
                "consistency_result": consistency_result,
            }

            return generate_cs_response(
                user_input=user_input,
                sub_intent="payment_confirmation",
                response_mode="narrative_guidance",
                result=combined_result,
                policy_context=(
                    PAYMENT_COMPLETION_POLICY_CONTEXT
                    + "\n\n"
                    + ORDER_PAYMENT_CONSISTENCY_POLICY_CONTEXT
                ),
            )

    return generate_cs_response(
        user_input=user_input,
        sub_intent="payment_confirmation",
        response_mode="fact_summary",
        result=result,
        policy_context=PAYMENT_COMPLETION_POLICY_CONTEXT,
    )

# =========================================================
# 배송 상태 확인 최종 응답 생성
# =========================================================

def build_delivery_status_response(
    user_input: str,
    result: dict,
) -> str:
    """
    배송 상태 조회 결과를 사용자 응답으로 변환한다.

    - 조회 성공:
      확인된 배송 상태만 안내한다.

    - 주문 선택 필요:
      Python에서 후보 주문을 안내한다.

    - 조회 실패:
      Python에서 조회 실패를 안내한다.
    """

    result_type = result["result_type"]

    # 주문을 찾지 못한 경우
    if result_type == "not_found":
        return (
            "배송 상태를 확인할 주문을 찾을 수 없습니다. "
            "주문번호를 다시 확인해 주세요."
        )

    # 주문이 여러 건인 경우
    if result_type == "need_order_selection":
        candidate_orders = result["candidate_orders"]

        order_list = "\n".join(
            f"- 주문번호 {order['order_id']} / "
            f"{order['order_date']} / "
            f"{order['total_price']:,}원"
            for order in candidate_orders
        )

        return (
            "배송 상태를 확인할 주문을 선택해 주세요.\n\n"
            f"{order_list}"
        )

    # 예상하지 못한 결과
    if result_type != "success":
        return "배송 상태를 확인하는 중 문제가 발생했습니다."

    order_status = result["order_status"]
    delivery_status = result["delivery_status"]
    order_id = result["order_id"]

    # 취소된 주문
    if order_status == "order_canceled":
        return (
            f"주문번호 {order_id}번은 취소된 주문입니다. "
            "현재 진행 중인 배송은 없습니다."
        )

    # 주문 실패
    if order_status == "order_failed":
        return (
            f"주문번호 {order_id}번은 정상적으로 완료되지 않은 주문입니다. "
            "현재 진행 중인 배송은 없습니다."
        )

    # 배송 준비중
    if delivery_status == "preparing_shipment":
        return (
            f"주문번호 {order_id}번은 현재 배송 준비 중입니다."
        )

    # 배송중
    if delivery_status == "in_transit":
        return (
            f"주문번호 {order_id}번은 현재 배송 중입니다."
        )

    # 배송완료
    if delivery_status == "delivered":
        return (
            f"주문번호 {order_id}번은 배송이 완료되었습니다."
        )

    # 정의되지 않은 배송 상태
    return (
        f"주문번호 {order_id}번의 배송 상태를 "
        "현재 정확하게 안내하기 어렵습니다."
    )

# =========================================================
# 일반 배송 예상 시기 안내 응답
# =========================================================

def build_general_delivery_eta_response(
    policy_result: dict,
) -> str:
    """
    일반적인 배송기간 Policy를 사용자 안내 문장으로 변환한다.
    """

    standard_days = policy_result["standard_delivery_days"]
    remote_days = policy_result["remote_area_delivery_days"]

    return (
        "일반 지역은 배송 시작일 기준 "
        f"{standard_days} 정도 소요됩니다. "
        "제주 및 도서산간 지역은 배송 시작일 기준 "
        f"{remote_days} 정도 소요될 수 있습니다. "
        "실제 배송 일정은 주문 및 배송 상황에 따라 달라질 수 있습니다."
    )


# =========================================================
# 특정 주문 배송 예상 시기 안내 응답
# =========================================================

def build_order_delivery_eta_response(
    delivery_result: dict,
    eta_result: dict | None = None,
) -> str:
    """
    특정 주문의 실제 배송 상태와
    Delivery ETA Policy 판단 결과를 조합하여 응답한다.
    """

    result_type = delivery_result["result_type"]

    # 주문을 찾지 못한 경우
    if result_type == "not_found":
        return (
            "배송 예정 시기를 확인할 주문을 찾을 수 없습니다. "
            "주문번호를 다시 확인해 주세요."
        )

    # 여러 주문 중 선택이 필요한 경우
    if result_type == "need_order_selection":
        candidate_orders = delivery_result["candidate_orders"]

        order_list = "\n".join(
            f"- 주문번호 {order['order_id']} / "
            f"{order['order_date']} / "
            f"{order['total_price']:,}원"
            for order in candidate_orders
        )

        return (
            "배송 예정 시기를 확인할 주문을 선택해 주세요.\n\n"
            f"{order_list}"
        )

    # 예상하지 못한 조회 결과
    if result_type != "success":
        return "배송 예정 시기를 확인하는 중 문제가 발생했습니다."

    if eta_result is None:
        return "배송 예정 시기를 현재 정확하게 안내하기 어렵습니다."

    order_id = delivery_result["order_id"]
    judgment = eta_result["eta_judgment"]
    reason = eta_result.get("reason")

    # 취소된 주문 / 실패한 주문
    if judgment == "not_applicable":
        if reason == "order_canceled":
            return (
                f"주문번호 {order_id}번은 취소된 주문이므로 "
                "배송 예정 시기를 안내할 수 없습니다."
            )

        if reason == "order_failed":
            return (
                f"주문번호 {order_id}번은 정상적으로 완료되지 않은 주문이므로 "
                "배송 예정 시기를 안내할 수 없습니다."
            )

    # 이미 배송 완료
    if judgment == "already_delivered":
        return (
            f"주문번호 {order_id}번은 이미 배송이 완료되었습니다."
        )

    # 현재 상태 + 일반 배송 Policy 안내
    if judgment == "policy_guidance":
        standard_days = eta_result["standard_delivery_days"]
        remote_days = eta_result["remote_area_delivery_days"]

        if reason == "preparing_shipment":
            return (
                f"주문번호 {order_id}번은 현재 배송 준비 중입니다. "
                "배송이 시작된 이후 일반 지역은 "
                f"{standard_days}, 제주 및 도서산간 지역은 "
                f"{remote_days} 정도 소요될 수 있습니다."
            )

        if reason == "in_transit":
            return (
                f"주문번호 {order_id}번은 현재 배송 중입니다. "
                "일반 배송 기준은 배송 시작일 기준 "
                f"{standard_days}, 제주 및 도서산간 지역은 "
                f"{remote_days} 정도입니다. "
                "현재 데이터만으로 정확한 도착일은 확인하기 어렵습니다."
            )

    # 정의되지 않은 상태
    return (
        f"주문번호 {order_id}번의 배송 예정 시기를 "
        "현재 정확하게 안내하기 어렵습니다."
    )

# =========================================================
# 결제수단 변경 Policy 결과 → 사용자 응답
# =========================================================

def build_payment_method_change_response(result: dict) -> str:
    """
    결제 완료 후 결제수단 변경 요청에 대한
    Policy 결과를 사용자 안내 문장으로 변환한다.
    """

    judgment = result["payment_method_change_judgment"]
    recommended_action = result["recommended_action"]

    if (
        judgment == "not_changeable"
        and recommended_action == "cancel_and_reorder"
    ):
        return (
            "결제가 완료된 주문은 결제수단을 직접 변경할 수 없습니다. "
            "다른 결제수단을 이용하시려면 기존 주문을 취소한 후 "
            "원하시는 결제수단으로 다시 주문해 주세요."
        )

    return (
        "결제수단 변경 가능 여부를 확인하는 중 "
        "문제가 발생했습니다."
    )

# =========================================================
# 5. 이전 대화에서 처리 중인 State 확인
# =========================================================

def handle_pending_state(
    user_input: str,
    customer_id: int,
    orders: list[dict],
    state: dict,
    payments: list[dict] | None = None,
    refunds: list[dict] | None = None,
    payment_adjustments: list[dict] | None = None,
) -> dict | None:

    # 현재 기다리고 있는 후속 작업이 없는 경우
    if state["pending_action"] is None:
        return None


    delivery_address_result = handle_delivery_address_pending(
    user_input=user_input,
    customer_id=customer_id,
    orders=orders,
    state=state,
    )

    if delivery_address_result is not None:
        return delivery_address_result

    order_cancel_result = handle_order_cancel_pending(
        user_input=user_input,
        customer_id=customer_id,
        orders=orders,
        state=state,
        payments=payments,
        refunds=refunds,
    )

    if order_cancel_result is not None:
        return order_cancel_result


    order_change_result = handle_order_change_pending(
        user_input=user_input,
        customer_id=customer_id,
        orders=orders,
        state=state,
        payments=payments,
        refunds=refunds,
        payment_adjustments=payment_adjustments,
    )

    if order_change_result is not None:
        return order_change_result



    # -----------------------------------------------------
    # 공통 환불계좌 정보 입력
    # -----------------------------------------------------

    if state["pending_action"] == "collect_refund_account":

        selected_order_id = state["selected_order_id"]

        refund_id = state["pending_data"].get("refund_id")
        refund_amount = state["pending_data"].get("refund_amount")
        refund_type = state["pending_data"].get("refund_type")
        source = state["pending_data"].get("source")

        # 1. State 정보 확인

        if selected_order_id is None or refund_id is None:
            reset_state(state)

            return {
                "route": source or "refund",
                "result": {
                    "result_type": "action_failed",
                    "reason": "refund_state_not_found",
                },
                "response": (
                    "환불 정보를 확인할 수 없습니다. "
                    "환불 상태를 다시 확인해 주세요."
                ),
            }

        # 2. 사용자 입력에서 환불계좌 정보 추출

        account_info = extract_refund_account(user_input)

        if account_info is None:
            return {
                "route": source or "refund",
                "result": None,
                "response": (
                    "환불계좌 정보를 다음 형식으로 입력해 주세요.\n"
                    "은행명 / 계좌번호 / 예금주\n"
                    "예: 국민은행 / 1234567890 / 홍길동"
                ),
            }

        if refunds is None:
            refunds = []

        # 3. 공통 Refund Service에서 계좌 등록

        result = register_refund_account_common(
            refunds=refunds,
            refund_id=refund_id,
            bank_name=account_info["bank_name"],
            account_number=account_info["account_number"],
            account_holder=account_info["account_holder"],
        )

        # 4. 계좌 등록 성공

        if result["result_type"] == "success":

            reset_state(state)

            # 주문 수량 감소에 따른 부분 환불
            if source == "order_change":
                return {
                    "route": "order_change",
                    "result": result,
                    "response": (
                        "환불계좌가 정상적으로 등록되었습니다. "
                        f"주문번호 {result['order_id']}번의 "
                        f"부분 환불 금액 "
                        f"{result['refund_amount']:,}원은 "
                        "현재 환불 처리 중입니다."
                    ),
                }

            # 주문 취소에 따른 전체 환불
            if source == "order_cancel":
                return {
                    "route": "order_cancel",
                    "result": result,
                    "response": (
                        "환불계좌가 정상적으로 등록되었습니다. "
                        "계좌이체 환불은 현재 환불 처리 중입니다."
                    ),
                }

            # 정의되지 않은 Refund Source
            return {
                "route": "refund",
                "result": result,
                "response": (
                    "환불계좌가 정상적으로 등록되었습니다. "
                    "현재 환불 처리 중입니다."
                ),
            }

        # 5. 계좌 등록 실패

        reset_state(state)

        return {
            "route": source or "refund",
            "result": result,
            "response": (
                "환불계좌를 등록하는 중 문제가 발생했습니다. "
                "환불 상태를 다시 확인해 주세요."
            ),
        }

    # -----------------------------------------------------
    # 주문 완료 확인
    # -----------------------------------------------------

    if state["pending_action"] == "order_confirmation":

        selected_order_id = extract_order_id(user_input)

        # 주문번호를 찾지 못한 경우
        if selected_order_id is None:
            return {
                "route": "order_confirmation",
                "result": None,
                "response": "확인할 주문번호를 입력해주세요.",
            }

        candidate_order_ids = [
            order["order_id"]
            for order in state["candidate_orders"]
        ]

        # 후보에 없는 주문번호를 선택한 경우
        if selected_order_id not in candidate_order_ids:
            return {
                "route": "order_confirmation",
                "result": None,
                "response": (
                    "선택 가능한 주문번호 중에서 다시 선택해주세요."
                ),
            }

        # 정상적인 주문번호를 선택한 경우
        result = check_order_completion(
            orders=orders,
            customer_id=customer_id,
            order_id=selected_order_id,
        )

        consistency_result = None

        if (
            result.get("result_type") == "success"
            and payments is not None
        ):
            consistency_result = check_order_payment_consistency(
                orders=orders,
                payments=payments,
                customer_id=customer_id,
                order_id=selected_order_id,
            )

        response = build_order_confirmation_response(
            user_input=user_input,
            result=result,
            consistency_result=consistency_result,
        )

        # 하나의 작업이 끝났으므로 State 초기화
        reset_state(state)

        return {
            "route": "order_confirmation",
            "result": result,
            "response": response,
        }

    # -----------------------------------------------------
    # 결제 완료 확인
    # -----------------------------------------------------

    if state["pending_action"] == "payment_confirmation":

        selected_order_id = extract_order_id(user_input)

        # 주문번호를 찾지 못한 경우
        if selected_order_id is None:
            return {
                "route": "payment_confirmation",
                "result": None,
                "response": "결제를 확인할 주문번호를 입력해주세요.",
            }

        candidate_order_ids = [
            order["order_id"]
            for order in state["candidate_orders"]
        ]

        # 후보에 없는 주문번호를 선택한 경우
        if selected_order_id not in candidate_order_ids:
            return {
                "route": "payment_confirmation",
                "result": None,
                "response": (
                    "선택 가능한 주문번호 중에서 다시 선택해주세요."
                ),
            }

        if payments is None:
            payments = []

        result = check_payment_completion(
            orders=orders,
            payments=payments,
            customer_id=customer_id,
            order_id=selected_order_id,
        )

        consistency_result = None

        if result.get("result_type") == "success":
            consistency_result = check_order_payment_consistency(
                orders=orders,
                payments=payments,
                customer_id=customer_id,
                order_id=selected_order_id,
            )

        response = build_payment_confirmation_response(
            user_input=user_input,
            result=result,
            consistency_result=consistency_result,
        )

        # 작업 완료 후 State 초기화
        reset_state(state)

        return {
            "route": "payment_confirmation",
            "result": result,
            "response": response,
        }

    # -----------------------------------------------------
    # 배송 예상 시기 - 주문 선택
    # -----------------------------------------------------

    if state["pending_action"] == "delivery_eta_selection":

        selected_order_id = extract_order_id(user_input)

        # 주문번호를 확인할 수 없는 경우
        if selected_order_id is None:
            return {
                "route": "delivery_eta",
                "result": None,
                "response": (
                    "배송 예정 시기를 확인할 주문번호를 입력해 주세요."
                ),
            }

        # 사용자가 선택 가능한 주문인지 확인
        candidate_order_ids = [
            order["order_id"]
            for order in state["candidate_orders"]
        ]

        if selected_order_id not in candidate_order_ids:
            return {
                "route": "delivery_eta",
                "result": None,
                "response": (
                    "선택 가능한 주문번호가 아닙니다. "
                    "안내된 주문번호 중에서 다시 선택해 주세요."
                ),
            }

        # 선택한 주문의 실제 배송 상태 조회
        delivery_result = check_delivery_status(
            orders=orders,
            customer_id=customer_id,
            order_id=selected_order_id,
        )

        eta_result = None

        # 조회 성공 시 ETA Policy 판단
        if delivery_result["result_type"] == "success":
            eta_result = judge_order_delivery_eta(
                order_status=delivery_result["order_status"],
                delivery_status=delivery_result["delivery_status"],
            )

        response = build_order_delivery_eta_response(
            delivery_result=delivery_result,
            eta_result=eta_result,
        )

        # Read + Policy Flow가 끝났으므로 State 초기화
        reset_state(state)

        return {
            "route": "delivery_eta",
            "result": {
                "delivery_result": delivery_result,
                "eta_result": eta_result,
            },
            "response": response,
        }

    # -----------------------------------------------------
    # 배송 상태 확인 - 주문 선택
    # -----------------------------------------------------

    if state["pending_action"] == "delivery_status_selection":

        selected_order_id = extract_order_id(user_input)

        # 주문번호를 확인할 수 없는 경우
        if selected_order_id is None:
            return {
                "route": "delivery_status",
                "result": None,
                "response": (
                    "배송 상태를 확인할 주문번호를 입력해 주세요."
                ),
            }

        # 사용자가 선택 가능한 주문인지 확인
        candidate_order_ids = [
            order["order_id"]
            for order in state["candidate_orders"]
        ]

        if selected_order_id not in candidate_order_ids:
            return {
                "route": "delivery_status",
                "result": None,
                "response": (
                    "선택 가능한 주문번호가 아닙니다. "
                    "안내된 주문번호 중에서 다시 선택해 주세요."
                ),
            }

        # 선택한 주문의 배송 상태 조회
        result = check_delivery_status(
            orders=orders,
            customer_id=customer_id,
            order_id=selected_order_id,
        )

        response = build_delivery_status_response(
            user_input=user_input,
            result=result,
        )

        # Read Flow가 끝났으므로 State 초기화
        reset_state(state)

        return {
            "route": "delivery_status",
            "result": result,
            "response": response,
        }

# =========================================================
# 6. Router / Orchestrator
# =========================================================

def route_request(
    user_input: str,
    customer_id: int,
    orders: list[dict],
    state: dict,
    payments: list[dict] | None = None,
    refunds: list[dict] | None = None,
    payment_adjustments: list[dict] | None = None,
) -> dict:

    # -----------------------------------------------------
    # 1) 이전 대화에서 진행 중인 작업이 있는지 먼저 확인
    # -----------------------------------------------------

    pending_result = handle_pending_state(
        user_input=user_input,
        customer_id=customer_id,
        orders=orders,
        state=state,
        payments=payments,
        refunds=refunds,
        payment_adjustments=payment_adjustments,
    )

    if pending_result is not None:
        return pending_result

    # -----------------------------------------------------
    # 2) 진행 중인 작업이 없다면 새로운 질문으로 분류
    # -----------------------------------------------------

    request = classification_chain.invoke(
        {
            "user_input": user_input,
        }
    )

    # -----------------------------------------------------
    # 3) 주문 완료 확인
    # -----------------------------------------------------

    if (
        request.intent == "cs"
        and request.cs_category == "order_payment"
        and request.sub_intent == "order_confirmation"
    ):

        result = check_order_completion(
            orders=orders,
            customer_id=customer_id,
            order_id=request.order_id,
        )

        # 주문이 여러 개라 추가 질문이 필요한 경우
        if result["result_type"] == "need_order_selection":
            state["pending_action"] = "order_confirmation"
            state["candidate_orders"] = result["candidate_orders"]

        consistency_result = None

        if (
            result.get("result_type") == "success"
            and payments is not None
        ):
            consistency_result = check_order_payment_consistency(
                orders=orders,
                payments=payments,
                customer_id=customer_id,
                order_id=result["order_id"],
            )

        response = build_order_confirmation_response(
            user_input=user_input,
            result=result,
            consistency_result=consistency_result,
        )

        return {
            "route": "order_confirmation",
            "request": request.model_dump(),
            "result": result,
            "response": response,
        }

    # -----------------------------------------------------
    # 4) 결제 완료 확인
    # -----------------------------------------------------

    if (
        request.intent == "cs"
        and request.cs_category == "order_payment"
        and request.sub_intent == "payment_confirmation"
    ):

        if payments is None:
            payments = []

        result = check_payment_completion(
            orders=orders,
            payments=payments,
            customer_id=customer_id,
            order_id=request.order_id,
        )

        # 주문이 여러 개라 결제를 확인할 주문 선택이 필요한 경우
        if result["result_type"] == "need_order_selection":
            state["pending_action"] = "payment_confirmation"
            state["candidate_orders"] = result["candidate_orders"]

        consistency_result = None

        if result.get("result_type") == "success":
            consistency_result = check_order_payment_consistency(
                orders=orders,
                payments=payments,
                customer_id=customer_id,
                order_id=result["order_id"],
            )

        response = build_payment_confirmation_response(
            user_input=user_input,
            result=result,
            consistency_result=consistency_result,
        )

        return {
            "route": "payment_confirmation",
            "request": request.model_dump(),
            "result": result,
            "response": response,
        }

    # -----------------------------------------------------
    # 5) 주문 취소
    # -----------------------------------------------------

    if (
        request.intent == "cs"
        and request.cs_category == "order_payment"
        and request.sub_intent == "order_cancel"
    ):
        return start_order_cancel_flow(
            request=request,
            customer_id=customer_id,
            orders=orders,
            state=state,
        )
    # -----------------------------------------------------
    # 6) 배송지 변경
    # -----------------------------------------------------

    if (
        request.intent == "cs"
        and request.cs_category == "order_payment"
        and request.sub_intent == "delivery_address_change"
    ):
        return start_delivery_address_flow(
            request=request,
            customer_id=customer_id,
            orders=orders,
            state=state,
        )

    # =====================================================
    # 7) 결제수단 변경
    # =====================================================

    if (
    request.intent == "cs"
    and request.cs_category == "order_payment"
    and request.sub_intent == "payment_method_change"
    ):

        result = judge_payment_method_change()

        response = build_payment_method_change_response(result)

        return {
            "route": "payment_method_change",
            "request": request.model_dump(),
            "result": result,
            "response": response,
        }

    # -----------------------------------------------------
    # 8) 배송 상태 확인
    # -----------------------------------------------------

    if (
        request.intent == "cs"
        and request.cs_category == "delivery"
        and request.sub_intent == "delivery_status"
    ):

        result = check_delivery_status(
            orders=orders,
            customer_id=customer_id,
            order_id=request.order_id,
        )

        # 주문번호가 없고 주문이 여러 건인 경우
        if result["result_type"] == "need_order_selection":
            state["pending_action"] = "delivery_status_selection"
            state["candidate_orders"] = result["candidate_orders"]
            state["selected_order_id"] = None

        response = build_delivery_status_response(
            user_input=user_input,
            result=result,
        )

        return {
            "route": "delivery_status",
            "request": request.model_dump(),
            "result": result,
            "response": response,
        }

    # =========================================================
    # 9) 배송 예상 시기 - 일반 배송기간 안내
    # =========================================================

    if (
        request.intent == "cs"
        and request.cs_category == "delivery"
        and request.sub_intent == "delivery_eta"
        and request.delivery_eta_scope == "general"
    ):
        policy_result = get_general_delivery_eta_policy()

        response = build_general_delivery_eta_response(
            policy_result=policy_result,
        )

        return {
            "route": "delivery_eta",
            "request": request.model_dump(),
            "result": policy_result,
            "response": response,
        }

    # =========================================================
    # 10) 배송 예상 시기 - 특정 주문
    # =========================================================

    if (
        request.intent == "cs"
        and request.cs_category == "delivery"
        and request.sub_intent == "delivery_eta"
        and request.delivery_eta_scope == "order_specific"
    ):

        # 1. 실제 주문 및 배송 상태 조회

        delivery_result = check_delivery_status(
            orders=orders,
            customer_id=customer_id,
            order_id=request.order_id,
        )

        # 2. 주문이 여러 건이면 사용자에게 선택 요청

        if delivery_result["result_type"] == "need_order_selection":
            state["pending_action"] = "delivery_eta_selection"
            state["candidate_orders"] = delivery_result["candidate_orders"]
            state["selected_order_id"] = None

            response = build_order_delivery_eta_response(
                delivery_result=delivery_result,
                eta_result=None,
            )

            return {
                "route": "delivery_eta",
                "request": request.model_dump(),
                "result": delivery_result,
                "response": response,
            }

        # 3. 주문 조회 성공 시 ETA Policy 판단

        eta_result = None

        if delivery_result["result_type"] == "success":
            eta_result = judge_order_delivery_eta(
                order_status=delivery_result["order_status"],
                delivery_status=delivery_result["delivery_status"],
            )

        # 4. 실제 배송 상태 + ETA Policy를 조합해 응답

        response = build_order_delivery_eta_response(
            delivery_result=delivery_result,
            eta_result=eta_result,
        )

        return {
            "route": "delivery_eta",
            "request": request.model_dump(),
            "result": {
                "delivery_result": delivery_result,
                "eta_result": eta_result,
            },
            "response": response,
        }
    # =========================================================
    # 11) 주문 수량 변경
    # =========================================================

    if (
        request.intent == "cs"
        and request.cs_category == "order_payment"
        and request.sub_intent == "order_change"
    ):
        return start_order_change_flow(
            request=request,
            customer_id=customer_id,
            orders=orders,
            state=state,
            payments=payments,
        )

    # -----------------------------------------------------
    # 12) 아직 구현하지 않은 기능
    # -----------------------------------------------------

    return {
        "route": "not_implemented",
        "request": request.model_dump(),
        "result": None,
        "response": "아직 지원하지 않는 문의입니다.",
    }