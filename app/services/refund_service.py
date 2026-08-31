
def validate_refund_request(
    payments: list[dict],
    order_id: int,
    refund_type: str,
    refund_amount: int | None = None,
) -> dict:
    """
    실제 Refund 데이터를 생성하기 전에
    환불 요청이 처리 가능한지 검증한다.

    데이터는 변경하지 않는다.

    full refund에서 refund_amount가 전달되지 않으면
    실제 결제금액 전체를 환불금액으로 사용한다.
    """

    # 1. 결제정보 확인
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

    # 2. 환불 유형 검증
    if refund_type not in {"full", "partial"}:
        return {
            "result_type": "action_failed",
            "reason": "invalid_refund_type",
            "order_id": order_id,
        }

    # 3. 실제 환불금액 결정
    if refund_type == "full" and refund_amount is None:
        resolved_refund_amount = payment["payment_amount"]
    else:
        resolved_refund_amount = refund_amount

    if (
        resolved_refund_amount is None
        or resolved_refund_amount <= 0
    ):
        return {
            "result_type": "action_failed",
            "reason": "invalid_refund_amount",
            "order_id": order_id,
        }

    if resolved_refund_amount > payment["payment_amount"]:
        return {
            "result_type": "action_failed",
            "reason": "refund_amount_exceeds_payment",
            "order_id": order_id,
        }

    # 4. 지원 가능한 결제수단 확인
    payment_method = payment["payment_method"]

    if payment_method not in {"card", "cash"}:
        return {
            "result_type": "action_failed",
            "reason": "unsupported_payment_method",
            "order_id": order_id,
        }

    # 5. 검증 결과 반환
    return {
        "result_type": "success",
        "order_id": order_id,
        "payment_id": payment["payment_id"],
        "payment_method": payment_method,
        "payment_amount": payment["payment_amount"],
        "refund_type": refund_type,
        "refund_amount": resolved_refund_amount,
    }


# =========================================================
# 공통 환불 처리 Service
# =========================================================

def start_refund(
    payments: list[dict],
    refunds: list[dict],
    order_id: int,
    refund_amount: int | None,
    refund_type: str,
    refund_reason: str,
    adjustment_id: int | None = None,
) -> dict:
    """
    이미 환불 필요성이 확정된 이후
    공통 환불 절차를 시작한다.

    환불 가능 여부 검증은 validate_refund_request()에 위임하고,
    이 함수는 검증된 정보를 기준으로
    실제 Refund 데이터를 생성하고 상태를 결정한다.

    실제 PG 환불 완료 처리는 수행하지 않는다.
    """

    # -----------------------------------------------------
    # 1. 공통 Refund 검증
    # -----------------------------------------------------

    validation_result = validate_refund_request(
        payments=payments,
        order_id=order_id,
        refund_type=refund_type,
        refund_amount=refund_amount,
    )

    if validation_result["result_type"] != "success":
        return validation_result

    # 검증된 값을 사용한다.
    payment_id = validation_result["payment_id"]
    payment_method = validation_result["payment_method"]
    resolved_refund_amount = validation_result["refund_amount"]

    # -----------------------------------------------------
    # 2. Refund ID 생성
    # -----------------------------------------------------

    refund_id = (
        max(
            refund["refund_id"]
            for refund in refunds
        )
        + 1
        if refunds
        else 70001
    )

    # -----------------------------------------------------
    # 3. 결제수단에 따른 Refund 상태 결정
    # -----------------------------------------------------

    if payment_method == "card":
        refund_status = "refund_processing"
        result_type = "success"

    else:
        refund_status = "refund_account_required"
        result_type = "refund_account_required"

    # -----------------------------------------------------
    # 4. Refund 데이터 생성
    # -----------------------------------------------------

    refund = {
        "refund_id": refund_id,
        "payment_id": payment_id,
        "order_id": order_id,
        "refund_type": refund_type,
        "refund_amount": resolved_refund_amount,
        "refund_reason": refund_reason,
        "refund_status": refund_status,
        "adjustment_id": adjustment_id,
        "bank_name": None,
        "account_number": None,
        "account_holder": None,
    }

    refunds.append(refund)

    # -----------------------------------------------------
    # 5. 결과 반환
    # -----------------------------------------------------

    return {
        "result_type": result_type,
        "order_id": order_id,
        "payment_id": payment_id,
        "payment_method": payment_method,
        "refund_id": refund_id,
        "refund_type": refund_type,
        "refund_amount": resolved_refund_amount,
        "refund_reason": refund_reason,
        "refund_status": refund_status,
        "adjustment_id": adjustment_id,
    }

# =========================================================
# 환불계좌 등록
# =========================================================

def register_refund_account(
    refunds: list[dict],
    refund_id: int,
    bank_name: str,
    account_number: str,
    account_holder: str,
) -> dict:
    """
    환불계좌 입력이 필요한 환불 건에
    계좌정보를 등록한다.

    refund_id를 기준으로 특정 환불 건을 찾고,
    계좌정보 등록 후 refund_processing 상태로 변경한다.
    """

    # 1. 환불 데이터 확인
    refund = next(
        (
            refund
            for refund in refunds
            if refund["refund_id"] == refund_id
        ),
        None,
    )

    if refund is None:
        return {
            "result_type": "action_failed",
            "reason": "refund_not_found",
            "refund_id": refund_id,
        }

    # 2. 현재 환불 상태 재확인
    if refund["refund_status"] != "refund_account_required":
        return {
            "result_type": "action_failed",
            "reason": "invalid_refund_status",
            "refund_id": refund_id,
        }

    # 3. 계좌정보 검증
    if (
        not bank_name.strip()
        or not account_number.strip()
        or not account_holder.strip()
    ):
        return {
            "result_type": "action_failed",
            "reason": "invalid_refund_account",
            "refund_id": refund_id,
        }

    # 4. 계좌정보 저장
    refund["bank_name"] = bank_name.strip()
    refund["account_number"] = account_number.strip()
    refund["account_holder"] = account_holder.strip()

    refund["refund_status"] = "refund_processing"

    # 5. 결과 반환
    return {
        "result_type": "success",
        "refund_id": refund["refund_id"],
        "order_id": refund["order_id"],
        "payment_id": refund["payment_id"],
        "refund_type": refund["refund_type"],
        "refund_amount": refund["refund_amount"],
        "refund_status": refund["refund_status"],
        "bank_name": refund["bank_name"],
        "account_number": refund["account_number"],
        "account_holder": refund["account_holder"],
    }