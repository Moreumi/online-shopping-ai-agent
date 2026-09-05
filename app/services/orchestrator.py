from app.services.llm_service import classification_chain

from app.services.order_payment_service import (
    check_order_completion,
    generate_order_response,
    check_payment_completion,
    generate_payment_response,
    check_order_payment_consistency,
    check_order_change,
    change_order_quantity,
)

from app.policies.order_payment_consistency_policy import (
    ORDER_PAYMENT_CONSISTENCY_POLICY_CONTEXT,
)

from app.services.state_service import (
    reset_state,
    extract_order_id,
    extract_confirmation,
    extract_refund_account,
    extract_quantity_change_request,
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
    validate_refund_request,
    start_refund,
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
    return None


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

            # 사용자가 처음에 말한 수량 변경 요청을 보존
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

            # 승인 시 다시 사용할 변경 예정 정보
            state["pending_data"] = {
                "target_quantity": calculation["target_quantity"],
                "current_quantity": calculation["current_quantity"],
                "current_total_price": calculation["current_total_price"],
                "new_total_price": calculation["new_total_price"],
                "adjustment_type": calculation["adjustment_type"],
                "adjustment_amount": calculation["adjustment_amount"],
            }

        # 4. 변경 불가 / 취소 필요 / 오류 등
        #    → 더 진행할 State 없음

        else:
            reset_state(state)

        response = build_order_change_response(result)

        return {
            "route": "order_change",
            "request": request.model_dump(),
            "result": result,
            "response": response,
        }

    # -----------------------------------------------------
    # 12) 아직 구현하지 않은 기능
    # -----------------------------------------------------

    return {
        "route": "not_implemented",
        "request": request.model_dump(),
        "result": None,
        "response": "아직 지원하지 않는 문의입니다.",
    }