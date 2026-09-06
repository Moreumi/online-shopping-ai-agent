# Online Shopping Mall AI Agent

온라인 쇼핑몰에서 고객 문의를 이해하고, CS 응대와 상품 추천으로 연결할 수 있는 AI Agent의 전체 처리 흐름을 설계·구현하는 프로젝트입니다.

현재 CS 영역에서는 **주문 완료 확인 / 결제 완료 확인 / 결제수단 변경 / 주문 취소 / 주문 수량 변경 / 배송지 변경 / 배송 상태 확인 / 배송 예상 시기 안내**를 구현했습니다.

사용자 입력 이후 **Intent 판단 → Routing → State 관리 → Policy 판단 → Service 호출 → Write Action → 최종 응답**까지의 End-to-End 흐름을 연결했으며, 기능 구현 이후에는 Refund 책임 통합과 Feature Flow 분리를 통해 Orchestrator 구조를 개선했습니다.


---

## 1. Project Goal

단순히 LLM에게 사용자 질문을 전달해 답변을 생성하는 것이 아니라,

```text
사용자 질문
→ 질문 이해
→ Intent 판단
→ 필요한 기능 선택
→ 데이터 조회
→ Policy 판단
→ 결과 검증
→ 응답 방식 결정
→ 최종 응답 생성
```
까지 이어지는 전체 Chatbot Flow를 설계하고 구현하는 것을 목표로 합니다.

최종적으로 다음 두 기능을 지원하는 AI Agent를 개발합니다.

- 고객 CS 응대
- 고객 조건·상황·스타일에 따른 상품 추천

---

## 2. My Role

### Chatbot Flow / Agent Logic / Orchestration 설계 및 구현

사용자의 질문이 들어온 이후 최종 답변이 생성될 때까지의
전체 처리 흐름을 설계하고 각 Component를 연결하는 역할을 담당합니다.

주요 담당 영역:

- Intent Classification 및 Routing 구조 설계
- CS / 상품추천 처리 흐름 설계
- Component 간 Input / Output 정의
- 멀티턴 대화를 위한 State 관리
- Service / Policy / LLM 호출 순서 설계
- Policy 기반 Business Rule 적용
- 기능 간 Orchestration 구현
- End-to-End 테스트 및 개선

---

## 3. Current Implementation

현재 구현된 CS 기능은 다음과 같습니다.

### 주문 완료 확인

```text
사용자 질문
→ Intent Classification
→ 주문 조회
→ Order Completion Policy
→ 주문-결제 Consistency 검증
→ Response Mode 결정
→ 최종 응답
```

### 결제 완료 확인

```text
사용자 질문
→ Intent Classification
→ 결제 조회
→ Payment Completion Policy
→ 주문-결제 Consistency 검증
→ Response Mode 결정
→ 최종 응답
```

주문이 여러 건 존재하는 경우에는
Agent가 임의로 주문을 선택하지 않고 사용자에게 주문번호를 추가로 확인합니다.

### 결제수단 변경

```text
사용자 질문
→ Intent Classification
→ Payment Method Change Policy
→ 결제수단 직접 변경 불가 판단
→ 취소 후 재주문 안내
→ Flow 종료
```

결제가 완료된 주문의 결제수단은 직접 변경할 수 없다는
Business Rule을 안내하는 Guidance Flow로 구현했습니다.

이 기능에서는 주문 조회나 State를 사용하지 않으며,
주문 취소를 자동으로 실행하지 않습니다.

사용자가 이후 별도로 주문 취소를 요청하면
새로운 Intent Classification을 거쳐
기존 `order_cancel` Flow로 진입합니다.

### 주문 취소

```text
사용자 질문
→ Intent Classification
→ 주문 조회
→ Order Cancel Policy
→ 취소 가능 여부 판단
→ 사용자 최종 승인
→ Action 직전 Order Cancel Policy 재검증
→ 결제 상태 재검증
→ 주문 / 결제 취소 Action
→ 결제 방식에 따른 Refund Flow
→ 최종 응답
```

주문 취소처럼 실제 데이터를 변경하는 기능은
Policy에서 취소 가능하다고 판단되더라도 바로 실행하지 않습니다.

사용자의 명확한 최종 승인을 확인한 이후에만
Write Action 실행 단계로 이동합니다.

또한 최초 Policy 판단과 사용자의 최종 승인 사이에
실제 배송 상태가 변경될 수 있으므로,
Action 실행 직전에 현재 주문 상태와 배송 상태를 기준으로
Order Cancel Policy를 다시 적용합니다.

예를 들어 최초 확인 시 배송 준비중이어서 취소 가능했더라도
사용자 승인 전에 배송이 시작되었다면
주문 취소 Action을 실행하지 않습니다.

결제 상태 역시 Action 직전에 다시 확인하며,
모든 재검증을 통과한 경우에만
실제 주문 및 결제 상태를 변경합니다.

카드 결제는 취소 후 `refund_processing` 상태로 전환하고,
계좌이체는 환불계좌 정보를 추가로 입력받은 뒤
`refund_processing` 상태로 전환합니다.

### 배송지 변경

```text
사용자 질문
→ Intent Classification
→ 주문 조회 / 선택
→ Delivery Address Change Policy
→ 새 배송지 수집
→ State 임시 저장
→ 사용자 최종 승인
→ Action 직전 상태 재검증
→ 배송지 변경 Action
→ 최종 응답
```

배송지 변경은 실제 주문 데이터를 수정하는 Write Action이므로
변경 가능 여부가 확인되더라도 즉시 실행하지 않습니다.

사용자가 입력한 새 배송지는 `pending_data`에 임시 저장하고,
변경 전·후 배송지를 확인한 뒤 사용자의 최종 승인을 받습니다.

또한 최초 판단 이후 배송이 시작되는 상황을 방지하기 위해
실제 Action 실행 직전에 주문 상태와 배송 상태를 다시 확인합니다.

### 주문 수량 변경

```text
사용자 질문
→ Intent Classification
→ 주문 / 결제 조회
→ Order Change Policy
→ 수량 변경 가능 여부 판단
→ 목표 수량 및 주문금액 계산
→ 결제 차액 계산
→ 변경 Preview
→ 사용자 최종 승인
→ Action 직전 주문 / 배송 / 결제 상태 재검증
→ 주문 수량 및 주문금액 변경
→ Payment Adjustment 생성
→ 차액 유형에 따른 후속 Flow 분기
    ├─ 추가 결제 필요
    │   → additional_payment_required
    │   → 추가 결제 대기
    │
    └─ 부분 환불 필요
        → partial_refund_required
        → Refund Flow
        ├─ 카드: refund_processing
        └─ 계좌이체: refund_account_required
            → 환불계좌 입력
            → refund_processing
→ 최종 응답
```

따라서 수량 변경으로 주문금액이 달라져도
기존 payment_amount를 임의로 수정하지 않습니다.

또한 Preview 이후 사용자에게 최종 승인을 받고,
Action 실행 직전에 주문 상태, 배송 상태, 결제 상태를 다시 확인한 뒤
조건이 유지되는 경우에만 실제 Write Action을 실행합니다.

### 배송 상태 확인

```text
사용자 질문
→ Intent Classification
→ Delivery Routing
→ 주문 조회 / 선택
→ Delivery Status 조회
→ 배송 상태 응답
```
### 배송 예상 시기 안내

배송 예상 시기 문의는 질문이 특정 주문을 대상으로 하는지에 따라
두 가지 처리 경로로 분리합니다.

#### 일반 배송기간 문의

```text
사용자 질문
→ Intent Classification
→ delivery_eta / general
→ Delivery ETA Policy
→ 일반 배송기간 안내
→ Flow 종료
```

예를 들어 `"배송은 보통 얼마나 걸려?"`와 같은 질문은
특정 주문 데이터가 필요하지 않으므로 주문 조회나 State를 사용하지 않습니다.

현재 MVP의 일반 배송 기준은
배송 시작일 기준 일반 지역 `3~5 영업일`,
제주 및 도서산간 지역 `최대 7일`입니다.

#### 특정 주문의 배송 예상 시기 문의

```text
사용자 질문
→ Intent Classification
→ delivery_eta / order_specific
→ 주문 조회 / 선택
→ Delivery Status 조회
→ Delivery ETA Policy
→ 실제 배송 상태 + 일반 배송 기준 조합
→ 최종 응답
```

`"내 주문 언제 와?"`, `"10004번 주문 언제 도착해?"`처럼
실제 주문을 대상으로 하는 질문은 기존 Delivery Service를 재사용하여
현재 `order_status`와 `delivery_status`를 먼저 확인합니다.

주문이 여러 건 존재하면 Agent가 임의로 주문을 선택하지 않고,
State에 후보 주문을 저장한 뒤 사용자에게 주문번호를 추가로 확인합니다.

현재 MVP에는 택배사 실시간 Tracking 정보나
확정 배송 예정일 데이터가 없으므로,
실제 데이터에 존재하지 않는 정확한 도착 날짜나 현재 배송 위치를
임의로 추정하지 않습니다.

## 4. Current Architecture

현재 구조는 Orchestrator가 모든 Multi-turn 세부 로직을 직접 처리하지 않고, 복잡한 기능은 Feature Flow에 위임하도록 구성되어 있습니다.

```text
User
↓
FastAPI Router
↓
Orchestrator
├─ 진행 중인 대화 흐름 확인
├─ Intent Classification
├─ Routing
└─ 실행할 Feature / Handler 선택
    │
    ├─ Read / Guidance Flow
    │   ├─ order_confirmation
    │   ├─ payment_confirmation
    │   ├─ payment_method_change
    │   ├─ delivery_status
    │   └─ delivery_eta
    │
    └─ Feature Flow
        ├─ Delivery Address Flow
        ├─ Order Cancel Flow
        └─ Order Change Flow
             ↓
           Service
             ↓
           Policy / Validation
             ↓
           Data Action
             ↓
           Response
```

복잡한 Write 기능은 별도의 Feature Flow에서 Multi-turn State와 세부 진행 순서를 관리합니다.

```text
Orchestrator
→ 어떤 기능을 실행할지 결정

Feature Flow
→ 기능 내부의 Multi-turn State 전이
→ 사용자 추가 입력 수집
→ 최종 승인 확인
→ Service 호출 순서 관리
→ 다른 공통 Flow로의 연결

Service
→ 주문·결제·환불 등 실제 데이터 조회 및 변경

Policy
→ 현재 상태를 기준으로 업무 가능 여부 판단

LLM
→ Intent 분류 및 확정된 결과의 자연어 표현
```

### Feature Flow Layer

현재 다음과 같은 복잡한 Multi-turn 기능을 Feature Flow로 분리했습니다.

```text
app/flows/
├─ delivery_address_flow.py
├─ order_cancel_flow.py
└─ order_change_flow.py
```

예를 들어 주문 수량 변경은 다음 과정을 하나의 Feature Flow가 관리합니다.

```text
Order Change 요청
↓
주문 선택 필요 여부 확인
↓
수량 입력 필요 여부 확인
↓
변경 Preview 생성
↓
사용자 최종 승인
↓
주문 변경 Write Action
↓
추가 결제 / 부분 환불 분기
↓
필요 시 공통 Refund Flow 연결
```

환불계좌 입력인 `collect_refund_account`는 주문 취소와 주문 수량 변경에서 함께 사용되므로 특정 Feature Flow에 종속시키지 않고 공통 Refund State로 유지했습니다.

### 역할 분리 기준

**Orchestrator**

* Intent와 현재 State를 기준으로 실행할 기능을 결정
* Feature Flow 또는 공통 Handler로 요청 전달
* 전체 기능 간 연결 책임 담당

**Feature Flow**

* 특정 기능의 Multi-turn 진행 과정 관리
* State 전이 및 추가 입력 처리
* 사용자 승인과 Write Action 사이의 실행 순서 관리

**Service / Data**

* 고객·주문·결제·배송·환불 데이터 조회
* 실제 Write Action 수행

**Policy**

* 조회된 상태값을 기준으로 업무 가능 여부 판단

**Consistency Policy**

* 주문·결제 등 서로 연결된 데이터의 상태 불일치 검증

**LLM**

* 사용자 Intent 및 필요한 조건 추출
* 확정된 사실과 Policy 결과를 자연어로 표현

업무 가능 여부와 실제 상태 변경은 LLM이 임의로 결정하지 않으며, Python 기반 Policy와 Service 결과를 기준으로 처리합니다.

### Architecture Optimization

기능 구현 이후 Orchestrator에 Multi-turn State 처리와 세부 Business Flow가 집중되어 있어, 기능 추가·수정 시 하나의 파일에서 확인해야 하는 범위가 커지는 문제를 발견했습니다.

이를 두 단계로 개선했습니다.

#### 1. Refund Responsibility 통합

주문 취소와 주문 수량 감소에서 각각 구현되어 있던 Refund 처리를 공통 `refund_service.py`로 통합했습니다.

```text
Before
Order Cancel ─→ 자체 Refund 처리
Order Change ─→ 별도 Refund 처리

After
Order Cancel ─┐
              ├─→ Refund Service
Order Change ─┘
```

| 항목                | Before | After |
| ----------------- | -----: | ----: |
| Refund 생성 구현 위치   |      2 |     1 |
| 환불계좌 등록 구현 위치     |      2 |     1 |
| card / cash 분기 위치 |      2 |     1 |
| 환불계좌 입력 State     |      2 |     1 |

#### 2. Orchestrator 책임 분리

Orchestrator가 직접 관리하던 복잡한 Multi-turn Flow를 Feature Flow Layer로 분리했습니다.

```text
Before

Orchestrator
├─ Routing
├─ Delivery Address 상세 Flow
├─ Order Cancel 상세 Flow
├─ Order Change 상세 Flow
└─ Pending State 처리


After

Orchestrator
→ Feature 선택 / 연결

Feature Flow
→ Multi-turn State / 업무 흐름

Service
→ 실제 데이터 Action
```

분리한 Feature Flow:

* `delivery_address_flow.py`
* `order_cancel_flow.py`
* `order_change_flow.py`

최종 측정 결과:

| 측정 항목                          |     Before |      After |
| ------------------------------ | ---------: | ---------: |
| `orchestrator.py` Line 수       |      2,707 |      1,194 |
| Orchestrator 직접 Pending Action |         13 |          5 |
| 전체 Regression Test             | 144 passed | 146 passed |

`orchestrator.py`는 2,707줄에서 1,194줄로 약 **55.9% 감소**했습니다.

단, 이 수치는 Feature Flow 분리뿐 아니라 리팩터링 과정에서 발견한 unreachable code, 중복 Response Builder, unused import 제거가 함께 포함된 결과입니다. 따라서 코드 Line 감소 자체보다 **Orchestrator → Feature Flow → Service로 책임 경계를 명확히 한 것**을 주요 개선 결과로 봅니다.

리팩터링 과정에서 기존 Order Change Flow의 State 초기화 로직이 누락된 것도 발견하여 복구하고, 동일 문제가 다시 발생하지 않도록 Regression Test를 추가했습니다.

세부 최적화 과정과 Before / After 기록은 `docs/optimization.md`에서 확인할 수 있습니다.



## 5. Key Design Decisions

### Policy와 LLM의 책임 분리

업무 상태 판정은 Python Business Rule에서 수행하고,
LLM은 확정된 결과를 표현하는 역할만 담당합니다.

```text
Data
→ Policy 판단
→ 확정 Result
→ LLM 표현
```

### 주문과 결제의 Consistency 검증

개별 상태만 정상이라고 해서 최종적으로 정상 처리된 것으로 판단하지 않습니다.

예:

```text
order_status = order_completed
payment_status = payment_failed

→ needs_review
```

이 경우 정상 완료 응답을 차단하고 추가 확인이 필요한 상태로 처리합니다.

### Hybrid Response Generation

모든 메시지를 LLM으로 생성하지 않습니다.

```text
주문번호 선택 요청 등 Flow Control
→ Python

확정된 고객 결과 설명
→ Output Prompt + LLM
```

### 응답 형식 분리

객관적인 조회 결과와 설명이 필요한 상황의 출력 형식을 분리했습니다.

```text
fact_summary
→ 주문/결제 상태 등 객관적인 정보 전달

narrative_guidance
→ Policy, 예외, 데이터 불일치 설명
```

### 기능의 성격에 따른 Flow 분리

모든 CS 기능에 동일한 처리 구조를 적용하지 않습니다.

```text
Read Flow
→ 실제 데이터 조회가 필요한 기능

Guidance Flow
→ Business Policy 안내만 필요한 기능

Write Flow
→ 실제 데이터 변경이 필요한 기능
```

예를 들어 결제수단 변경은
결제 완료 후 직접 변경할 수 없다는 정책 안내가 핵심이므로
불필요한 주문 조회, State, 사용자 승인, Write Action을 추가하지 않았습니다.

### 주문금액과 실제 결제금액의 분리

주문 수량이 변경되었다고 해서
실제 결제가 즉시 완료된 것으로 처리하지 않습니다.

예를 들어 기존 3개, 60,000원 주문을 2개, 40,000원으로 변경하면:

```text
orders.total_price
60,000 → 40,000
→ 변경된 주문의 현재 금액

payments.payment_amount
60,000 유지
→ 실제로 이미 결제된 금액

payment_adjustments
20,000 / partial_refund_required / pending
→ 외부 결제 시스템에서 이후 처리해야 할 차액
```

이를 통해 주문 데이터 변경과 실제 결제 처리를 분리하고,
외부 PG 연동이 없는 MVP에서 결제 완료 상태를 임의로 생성하지 않도록 했습니다.


---

## 6. Project Structure

```text
app/
├── data/
│   └── sample_data.py
│       # MVP 테스트용 주문 / 결제 / 환불 / 결제 차액 데이터
│
├── policies/
│   ├── order_completion_policy.py
│   ├── payment_completion_policy.py
│   ├── order_payment_consistency_policy.py
│   ├── order_cancel_policy.py
│   ├── order_change_policy.py
│   ├── delivery_address_change_policy.py
│   └── payment_method_change_policy.py
│       # Business Rule 및 상태 판단
│
├── routers/
│   ├── chat.py
│   └── health.py
│       # FastAPI Endpoint
│
├── schemas/
│   └── chat.py
│       # 사용자 요청 Structured Output / Schema
│
├── services/
│   ├── llm_service.py
│   ├── order_payment_service.py
│   ├── delivery_service.py
│   ├── response_service.py
│   ├── state_service.py
│   └── orchestrator.py
│       # LLM, 데이터 조회, State, Response, 전체 Orchestration
│
└── main.py
    # FastAPI Application

docs/
├── architecture.md
│   # 현재 Chatbot Architecture
│
├── architecture_evolution.md
│   # 주요 구조 변경과 설계 결정 기록
│
├── order_confirmation_e2e.md
├── payment_confirmation_e2e.md
├── output_response_design.md
│
└── policies/
    ├── order_completion_policy_v1.md
    ├── payment_completion_policy_v1.md
    ├── order_payment_consistency_policy_v1.md
    ├── order_cancel_policy_v1.md
    ├── delivery_address_change_policy_v1.md
    └── payment_method_change_policy_v1.md

tests/
├── test_*_policy.py
│   # Business Policy 단위 테스트
│
├── test_*_service.py
│   # Service 조회 / 처리 테스트
│
├── test_*_state.py
│   # Multi-turn State 테스트
│
├── test_*_action.py
│   # Write Action 및 Action 직전 재검증 테스트
│
├── test_*_flow.py
│   # Routing / Multi-turn Flow 테스트
│
└── test_*_e2e.py
    # End-to-End 통합 테스트
```

기능별 파일을 단순히 나열하는 것보다
각 Layer와 테스트의 책임이 드러나도록 구조를 관리합니다.
---

## 7. Tech Stack

- Python
- FastAPI
- LangChain
- OpenAI LLM
- Pydantic
- pytest
- Git / GitHub

---

## 8. How to Run

### 패키지 설치

```bash
pip install -r requirements.txt
```

### 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 OpenAI API Key를 설정합니다.

```text
OPENAI_API_KEY=your_api_key
```

`.env` 파일은 Git에 업로드하지 않습니다.

### FastAPI 실행

```bash
uvicorn app.main:app --reload
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

---

## 9. Test

전체 테스트 실행:

```bash
python -m pytest -v
```

현재 테스트에서는 다음 흐름을 검증합니다.

- 주문 완료 확인 멀티턴 Flow
- 결제 완료 확인 멀티턴 Flow
- 주문 완료 + 결제 실패 상태의 Consistency Routing
- 주문 실패 + 결제 완료 상태의 Consistency Routing

- 주문 취소 가능 여부 Policy
- 사용자 승인 / 거절 / 불명확 응답 처리
- 카드 주문 취소 Action
- 계좌이체 주문 취소 및 환불계좌 수집
- 주문 취소 Action 직전 주문 / 배송 상태 재검증
- 주문 취소 Multi-turn Flow
- FastAPI Swagger 기반 주문 취소 End-to-End Flow

- 배송지 변경 가능 여부 Policy
- 배송지 변경 대상 주문 선택 Flow
- 새 배송지 수집 및 State 임시 저장
- 배송지 변경 승인 / 거절 / 불명확 응답 처리
- 배송지 변경 Write Action
- Action 직전 주문 / 배송 상태 재검증
- 배송지 변경 Multi-turn End-to-End Flow
- FastAPI Swagger 기반 배송지 변경 End-to-End Flow

- 결제수단 변경 Policy
- 결제수단 변경 Guidance Routing
- 결제수단 변경 안내 후 State 미생성 확인
- 결제수단 변경 안내 종료 후 별도 주문 취소 요청이 기존 `order_cancel` Flow로 진입하는지 검증

- 배송 상태 조회 Service
- 명시적 주문번호 기반 배송 상태 조회
- 단일 주문 자동 선택
- 다중 주문의 주문 선택 요청
- 배송 상태 Routing
- 배송 상태 조회 Multi-turn State 처리
- 잘못된 주문 선택 시 State 유지
- 배송 상태 Multi-turn End-to-End Flow
- FastAPI Swagger 기반 배송 상태 End-to-End Flow

현재 전체 테스트 71개가 통과합니다.

---

## 10. Documentation

상세 설계는 `docs/`에서 확인할 수 있습니다.

- `docs/architecture.md`
  - 현재 Chatbot Architecture와 Component별 역할

- `docs/architecture_evolution.md`
  - 주요 구조 변경의 문제, 설계 결정, 변경 이유 기록

- `docs/output_response_design.md`
  - Policy / Consistency / Output Response 구조

- `docs/policies/delivery_address_change_policy_v1.md`
  - 배송지 변경 가능 조건 및 Write Action 실행 원칙

- `docs/policies/order_cancel_policy_v1.md`
  - 주문 취소 가능 조건, 사용자 승인 및 Action 직전 재검증 원칙

- `docs/order_confirmation_e2e.md`
  - 주문 완료 확인 End-to-End 처리 흐름

- `docs/payment_confirmation_e2e.md`
  - 결제 완료 확인 End-to-End 처리 흐름

- `docs/policies/`
  - 주문 / 결제 / Consistency Policy 정의

- `docs/policies/payment_method_change_policy_v1.md`
  - 결제 완료 후 결제수단 변경 불가 및 취소 후 재주문 정책

---

## 11. Next Steps

현재 CS의 주문·결제 확인 기능을 기준으로 전체 Agent 구조를 검증하고 있습니다.

향후 다음 영역으로 확장할 예정입니다.

- 주문/결제 CS 세부 기능 확장
- 배송 세부 기능 / 교환 / 환불 / 상품정보 CS 확장
- 상품 추천 Flow
- 실제 DB 연동
- State 관리 구조 확장
- 전체 End-to-End 테스트 확대