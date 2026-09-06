from app.schemas.chat import UserRequest
from app.data.sample_data import orders, payments
from app.flows.order_change_flow import start_order_change_flow


def test_start_order_change_flow_to_confirmation():

    state = {
        "pending_action": None,
        "candidate_orders": [],
        "selected_order_id": None,
        "pending_data": {},
    }

    request = UserRequest(
        intent="cs",
        cs_category="order_payment",
        sub_intent="order_change",
        quantity_change_type="decrease",
        quantity_value=1,
        order_id=10007,
    )

    result = start_order_change_flow(
        request=request,
        customer_id=6,
        orders=orders,
        state=state,
        payments=payments,
    )

    assert result["route"] == "order_change"
    assert result["result"]["result_type"] == "change_preview"

    assert state["pending_action"] == "order_change_confirmation"
    assert state["selected_order_id"] == 10007

    assert state["pending_data"]["target_quantity"] == 2
    assert state["pending_data"]["adjustment_amount"] == 20000

    assert "3개에서 2개로 변경" in result["response"]
    assert "부분 환불 예정 금액: 20,000원" in result["response"]

def test_start_order_change_flow_resets_stale_state_when_order_not_found():
    state = {
        "pending_action": "order_change_confirmation",
        "candidate_orders": [{"order_id": 10007}],
        "selected_order_id": 10007,
        "pending_data": {
            "target_quantity": 2,
        },
    }

    request = UserRequest(
        intent="cs",
        cs_category="order_payment",
        sub_intent="order_change",
        quantity_change_type="decrease",
        quantity_value=1,
        order_id=99999,
    )

    result = start_order_change_flow(
        request=request,
        customer_id=6,
        orders=orders,
        state=state,
        payments=payments,
    )

    assert result["result"]["result_type"] == "not_found"
    assert state["pending_action"] is None
    assert state["candidate_orders"] == []
    assert state["selected_order_id"] is None
    assert state["pending_data"] == {}