# Optimization

이 문서는 온라인 쇼핑몰 AI Agent의 기능 구현 이후
구조와 실행 흐름을 최적화하는 과정에서

- 어떤 비효율을 발견했는지
- 어떤 기준으로 개선 대상을 선택했는지
- 최적화 전후 구조가 어떻게 달라졌는지
- 처리 단계, 중복 책임, 응답 시간 등이 얼마나 변화했는지

를 Before / After 기준으로 기록한다.

단순한 코드 축소를 목표로 하지 않고,
기존 기능의 정확성과 Write Action의 안전성을 유지하면서
불필요한 처리와 중복 책임을 줄이는 것을 목표로 한다.

---

## 0. Optimization Baseline

### 0-1. 기준 Commit

```text
453a2f0
feat: implement order change and partial refund flow
```

해당 Commit을 기능 구현 완료 후
최적화를 시작하기 전의 기준 상태로 사용한다.

---

### 0-2. 구조 Baseline

| 측정 항목 | Before |
|---|---:|
| `orchestrator.py` Line 수 | 2,681 |
| `order_payment_service.py` Line 수 | 1,328 |
| `refund_service.py` Line 수 | 217 |
| 중앙 Orchestrator가 직접 처리하는 Pending Action | 14 |
| 전체 Regression Test | 140 passed |
| Regression Test 실행 시간 | 24.36s |

현재 중앙 Orchestrator는 총 14개의 `pending_action`을 직접 분기하여 처리한다.

이 값은 시스템 전체가 지원하는 Pending State의 수와는 구분한다.

- 전체 Pending Action 수: 시스템의 기능적 복잡성
- Orchestrator가 직접 처리하는 Pending Action 수: 중앙 제어기가 직접 관리하는 책임의 복잡성

따라서 이후 Handler 구조로 분리하더라도
Pending Action 자체가 없어졌다고 해석하지 않고,
중앙 Orchestrator가 직접 관리해야 하는 책임이 얼마나 감소했는지를 비교한다.

또한 Line 수 자체를 최적화 성공 기준으로 사용하지 않는다.

기능별 Handler 또는 Service 분리 과정에서
전체 코드량이 유지되거나 증가하더라도,
하나의 Component가 담당하는 책임과
기능 수정 시 확인해야 하는 범위가 감소했다면
구조적인 개선으로 평가한다.

---

### 0-3. Process Step 측정 기준

Process Step은 단순한 코드 한 줄을 의미하지 않는다.

다음과 같이 서로 다른 판단이나 처리가 발생하는 지점을
하나의 Process Step으로 본다.

```text
판단
데이터 조회
State 변경
Service 호출
Policy 확인
Write Action
```

단순 변수 저장이나 같은 작업을 위한 코드 Line 증가는
별도의 Process Step으로 계산하지 않는다.

또한 다음과 같은 안전 절차는
단계 수를 줄이기 위한 목적으로 제거하지 않는다.

```text
Policy 판단
→ 사용자 최종 승인
→ Action 직전 상태 재확인
→ 실제 Write Action
```

처리 단계 감소는 중복 조회, 중복 분기,
불필요한 Component 호출과 같이
동일한 목적을 반복하는 과정에 한해서 검토한다.

---

# 1. Refund Responsibility Optimization

## 1-1. 문제 발견

주문 취소와 주문 수량 감소 기능을 구현하면서
두 Flow 모두 환불 처리가 필요하게 되었다.

구현 이후 구조를 다시 확인한 결과,
환불과 관련된 동일한 역할이
두 Service에 나뉘어 존재하고 있었다.

```text
order_payment_service.py
→ 주문 취소
→ Refund 데이터 생성
→ 결제 방식에 따른 환불 상태 판단
→ 환불계좌 등록

refund_service.py
→ 부분 환불 생성
→ 결제 방식에 따른 환불 상태 판단
→ 환불계좌 등록
```

즉 주문 취소 과정에서 발생하는 환불과
주문 수량 감소 과정에서 발생하는 부분 환불이

각각 다른 위치에서 비슷한 방식으로 구현되어 있었다.

이 구조에서는 이후 환불 정책이나
환불 상태 처리 방법이 변경될 경우
두 Service를 모두 확인하고 수정해야 하는 문제가 발생한다.

---

## 1-2. Before 구조

최적화 이전의 환불 흐름은 다음과 같았다.

```text
[주문 취소]

Orchestrator
↓
order_payment_service.cancel_order()
├─ 주문 취소
├─ 결제 취소
├─ Refund 생성
├─ card / cash 분기
└─ Refund 상태 설정


[주문 수량 감소]

Orchestrator
↓
order_payment_service.change_order_quantity()
↓
Refund 필요 여부 판단
↓
refund_service.start_refund()
├─ Refund 생성
├─ card / cash 분기
└─ Refund 상태 설정
```

환불계좌 입력 역시 두 개의 Pending Action으로 나뉘어 있었다.

```text
주문 취소
→ collect_refund_account

주문 수량 감소
→ collect_partial_refund_account
```

실제로 최적화 전 코드를 확인한 결과는 다음과 같았다.

| 항목 | Before |
|---|---:|
| Refund 데이터 생성 구현 위치 | 2 |
| 환불계좌 등록 구현 위치 | 2 |
| card / cash Refund 분기 위치 | 2 |
| 환불계좌 입력 Pending Action | 2 |

---

## 1-3. 개선 시 고려한 사항

처음에는 중복 코드를 단순히 삭제하는 방향을 고려할 수 있었지만,
주문 취소는 실제 주문과 결제 상태를 변경하는 Write Action이기 때문에
환불 처리와의 연결 순서를 함께 고려해야 했다.

특히 다음 상황을 방지할 필요가 있었다.

```text
주문/결제 상태를 먼저 취소
↓
이후 Refund 처리를 시도
↓
지원하지 않는 결제 방식 등의 문제 발견
↓
주문은 취소되었지만 Refund를 시작하지 못함
```

따라서 단순히 함수를 분리하는 것이 아니라,
Write Action 이전에 Refund 처리 가능 여부를 먼저 확인하도록 구성하였다.

---

## 1-4. 개선 결정

환불과 관련된 공통 책임을
`refund_service.py` 하나에서 관리하도록 변경하였다.

각 Component의 역할은 다음과 같이 구분하였다.

```text
order_payment_service
→ 주문과 결제 데이터 변경

refund_service
→ Refund 검증
→ Refund 생성
→ 결제 방식에 따른 처리
→ 환불계좌 등록

orchestrator
→ 각 기능을 필요한 순서대로 연결
```

주문 취소 Flow는 다음 순서로 변경하였다.

```text
사용자 주문 취소 승인
↓
Refund 사전 검증
↓
주문 / 결제 취소 Action
↓
공통 Refund Service 호출
↓
카드 / 계좌이체 분기
```

이를 위해 Refund Service에
환불 가능 여부를 먼저 확인하는 기능을 추가하였다.

```text
validate_refund_request()
```

이 기능은 실제 데이터를 변경하지 않고

```text
Refund 종류
Refund 금액
결제 방식
결제 정보
```

등을 확인한 뒤
환불을 시작할 수 있는지 판단한다.

---

## 1-5. Refund 계좌 입력 Flow 통합

기존에는 전체 환불과 부분 환불의
계좌 입력 과정이 각각 존재했다.

### Before

```text
Order Cancel
→ collect_refund_account
→ 주문 취소 전용 환불계좌 등록

Order Change
→ collect_partial_refund_account
→ 부분 환불계좌 등록
```

두 과정 모두 실제로 수행하는 역할은 동일했다.

```text
사용자 계좌 입력
↓
Refund 확인
↓
계좌 정보 저장
↓
refund_processing 상태로 변경
```

따라서 두 Pending Action을 하나로 통합하였다.

### After

```text
Order Cancel ──────┐
                   │
Order Change ──────┤
                   ↓
          collect_refund_account
                   ↓
             Refund Service
                   ↓
        register_refund_account()
```

어떤 기능에서 발생한 Refund인지 구분하기 위해
State의 `pending_data`에 다음 Context를 저장하도록 구성하였다.

```python
{
    "refund_id": ...,
    "refund_amount": ...,
    "refund_type": "full" or "partial",
    "source": "order_cancel" or "order_change",
}
```

이를 통해 계좌 등록 과정은 공통으로 사용하면서도
처리가 끝난 뒤에는 원래 요청에 맞는 응답을 제공할 수 있도록 하였다.

---

## 1-6. After 구조

최적화 이후 구조는 다음과 같다.

```text
                  ┌─ Order Cancel
                  │
User Request ─────┤
                  │
                  └─ Order Change
                         ↓
                   Orchestrator
                         ↓
                  Refund 필요 판단
                         ↓
                   Refund Service
                  ├─ Refund 검증
                  ├─ Refund 생성
                  ├─ card / cash 판단
                  └─ 환불계좌 등록
```

`order_payment_service.py`에서는
Refund 생성과 환불계좌 등록 책임을 제거하였다.

현재 역할은 다음과 같이 분리된다.

```text
order_payment_service.py
→ 주문 / 결제 관련 데이터 처리

refund_service.py
→ Refund 관련 처리

orchestrator.py
→ 처리 순서와 기능 연결
```

---

## 1-7. 정량 비교

최적화 이후 동일한 검색 기준으로 다시 측정하였다.

| 측정 항목 | Before | After | 변화 |
|---|---:|---:|---:|
| Refund 데이터 생성 구현 위치 | 2 | 1 | 50% 감소 |
| 환불계좌 등록 구현 위치 | 2 | 1 | 50% 감소 |
| card / cash Refund 분기 위치 | 2 | 1 | 50% 감소 |
| 환불계좌 입력 Pending Action | 2 | 1 | 50% 감소 |
| `order_payment_service.py` | 1,328 lines | 1,211 lines | 117 lines 감소 |
| `refund_service.py` | 217 lines | 269 lines | 52 lines 증가 |
| `orchestrator.py` | 2,681 lines | 2,707 lines | 26 lines 증가 |

세 파일의 전체 Line 수는 다음과 같이 변화하였다.

```text
Before
2,681 + 1,328 + 217
= 4,226 lines

After
2,707 + 1,211 + 269
= 4,187 lines
```

전체적으로는 39 Line이 감소하였다.

하지만 이번 최적화에서는
전체 Line 수 감소를 핵심 성과로 판단하지 않는다.

`refund_service.py`의 Line 수가 증가한 이유는
기존에 여러 곳에 존재하던 Refund 책임을
하나의 Service로 모았기 때문이다.

또한 `orchestrator.py`는
Refund 사전 검증과 Service 연결 과정을 명시적으로 관리하면서
Line 수가 일부 증가하였다.

따라서 이번 최적화의 핵심 결과는

```text
같은 Refund 업무를 관리하는 위치
2곳 → 1곳
```

으로 줄였다는 점이다.

---

## 1-8. 사용자 관점

이번 최적화는 사용자의 대화 단계를 줄이기 위한 작업보다
내부 처리 책임을 정리하는 것을 우선 목표로 하였다.

따라서 사용자에게 필요한 안전 절차는 그대로 유지하였다.

```text
사용자 요청
↓
처리 가능 여부 확인
↓
사용자 최종 승인
↓
실제 Action 직전 재확인
↓
Write Action
```

계좌이체 환불의 경우에도
환불계좌가 필요한 상황에서는
기존과 동일하게 사용자에게 계좌정보를 추가로 요청한다.

따라서 현재 단계에서는
대화 Turn 감소를 이번 최적화의 성과로 판단하지 않는다.

실제 사용자 응답 시간은
추후 `/chat` 요청을 동일한 조건에서 반복 측정하여
Before / After를 비교할 예정이다.

---

## 1-9. 개발자 관점

이번 구조 변경을 통해
Refund 기능을 수정할 때 확인해야 하는 주요 위치를 줄였다.

### Before

```text
Refund 수정 시

order_payment_service.py 확인
+
refund_service.py 확인
```

### After

```text
Refund 수정 시

refund_service.py 중심으로 확인
```

특히 다음 구현 위치가 각각 2곳에서 1곳으로 감소하였다.

```text
Refund 생성
환불계좌 등록
결제 방식별 Refund 분기
```

따라서 이후 직접 환불 요청과 같은
새로운 Refund 기능을 추가할 경우에도
기존 주문 취소 또는 주문 변경 내부에
환불 로직을 다시 구현하지 않고
공통 Refund Service를 사용할 수 있는 구조가 되었다.

---

## 1-10. Regression Test 결과

구조 변경 이후 전체 Regression Test를 수행하였다.

| 항목 | Before | After |
|---|---:|---:|
| 전체 Test | 140 passed | 144 passed |
| 실패 | 0 | 0 |
| 단일 실행 시간 | 24.36s | 19.16s |

After Test 수가 증가한 이유는
공통 Refund 검증 기능과
분리된 주문 취소 Action을 검증하는 테스트를 추가하고,
기존 책임 구조에 의존하던 테스트를
새 구조에 맞게 정리했기 때문이다.

단일 실행에서는 전체 Regression Test 시간이

```text
24.36s
→
19.16s
```

로 감소하였다.

차이는 5.20초이며,
단일 실행 결과만 기준으로 계산하면
약 21% 짧아진 결과이다.

하지만 테스트 실행 시간은
PC 상태와 실행 환경에 따라 달라질 수 있기 때문에
현재 결과만으로 성능이 21% 향상되었다고 판단하지 않는다.

추후 동일한 조건에서 여러 차례 반복 측정하여
평균 실행 시간을 비교할 예정이다.

또한 이 값은 개발자가 전체 테스트를 수행하는 시간이며,
사용자가 실제 챗봇 응답을 기다리는 시간과는 구분한다.

사용자 관점의 응답 속도는
실제 API 요청 시간을 별도로 측정한다.

---

## 1-11. 현재 검증 결과

Refund 관련 주요 기능을 묶어
Target Test를 수행하였다.

```text
33 passed
```

이후 전체 Regression Test를 수행하였다.

```text
144 passed
0 failed
19.16s
```

검증된 주요 Flow는 다음과 같다.

```text
주문 취소
→ 전체 환불

주문 취소 + 계좌이체
→ 환불계좌 입력
→ 환불 처리

주문 수량 감소
→ 부분 환불

주문 수량 감소 + 계좌이체
→ 환불계좌 입력
→ 부분 환불 처리
```

현재까지 코드 수준의 Regression Test는 정상 통과하였다.

Swagger를 이용한 실제 `/chat` 요청 검증은
추가 확인 후 기록한다.

---

## 1-12. Optimization 1 결론

이번 최적화에서는
처리 단계를 무조건 줄이는 것보다
동일한 역할이 여러 위치에 중복되어 있는 문제를 우선 해결하였다.

최적화 전에는
주문 취소와 주문 변경이
각각 별도의 Refund 처리 방법을 가지고 있었지만,

최적화 이후에는
두 기능이 하나의 Refund Service를 공유하도록 변경하였다.

그 결과

```text
Refund 생성 위치             2 → 1
환불계좌 등록 구현 위치      2 → 1
결제 방식별 Refund 분기      2 → 1
환불계좌 입력 Pending Action 2 → 1
```

로 감소하였다.

기존 Write Action의 안전 절차와
사용자 대화 흐름은 유지하면서
Refund 관련 Business Logic의 관리 위치를 하나로 통합했다는 점을
이번 최적화의 주요 결과로 본다.

---

# 2. Orchestrator Structure Optimization

## 2-1. 문제 발견

Refund Responsibility Optimization 이후 `orchestrator.py`를 다시 확인한 결과, Orchestrator가 질문 유형에 따라 기능을 선택하는 역할뿐만 아니라 각 기능의 세부 Multi-turn 처리까지 직접 담당하고 있었다.

Optimization 2 시작 시점의 구조는 다음과 같았다.

```text
orchestrator.py
2,707 lines

Orchestrator가 직접 처리하는 Pending Action
13개
```

예를 들어 배송지 변경 기능에서는 Orchestrator가 다음 과정을 모두 직접 처리하고 있었다.

```text
배송지 변경 최초 요청 Routing
→ 변경할 주문 선택
→ 새로운 배송지 입력
→ 최종 승인
→ Write Action 연결
```

주문 취소 역시 다음 과정을 중앙 Orchestrator가 직접 관리했다.

```text
주문 취소 최초 요청 Routing
→ 취소할 주문 선택
→ 최종 승인
→ Refund 사전 검증
→ 주문 / 결제 취소
→ Refund Service 연결
```

기능이 추가될수록 `handle_pending_state()`에 새로운 분기가 계속 추가되는 구조였기 때문에, 특정 기능을 수정할 때 중앙 Orchestrator의 넓은 범위를 함께 확인해야 했다.

---

## 2-2. 개선 기준

이번 최적화에서는 Pending Action 자체를 없애는 것을 목표로 하지 않았다.

Pending Action은 Multi-turn 대화를 유지하기 위해 필요한 State이므로 그대로 유지하되, **어떤 Component가 해당 State의 세부 처리를 책임지는지**를 변경하였다.

목표 구조는 다음과 같이 정의하였다.

```text
Orchestrator
→ 어떤 Feature Flow를 실행할지 선택

Feature Flow
→ 해당 기능의 Multi-turn 처리
→ State 전환
→ 필요한 Service 연결

Service
→ 실제 Business Logic 및 데이터 처리
```

따라서 Orchestrator의 핵심 책임은 기능의 세부 구현이 아니라 **전체 처리 흐름에서 적절한 Feature Flow를 선택하고 연결하는 것**으로 정리하였다.

---

## 2-3. Feature Flow Layer 도입

기능별 Multi-turn 처리를 분리하기 위해 새로운 `flows` 계층을 추가하였다.

```text
app/
├─ flows/
│  ├─ delivery_address_flow.py
│  └─ order_cancel_flow.py
│
└─ services/
   └─ orchestrator.py
```

Service와 Flow의 역할은 다음 기준으로 구분하였다.

```text
Service
→ 실제 데이터 조회 / 검증 / 변경

Flow
→ 하나의 기능 안에서
   Service와 State를 순서대로 연결

Orchestrator
→ 어떤 Flow를 실행할지 결정
```

---

## 2-4. 배송지 변경 Flow 분리

배송지 변경 기능에서는 최초 요청과 다음 세 Pending Action을 `delivery_address_flow.py`로 이동하였다.

```text
delivery_address_change_selection
collect_delivery_address
confirm_delivery_address_change
```

### Before

```text
Orchestrator
├─ 배송지 변경 요청 판단
├─ 주문 선택
├─ 주소 입력
├─ 최종 승인
└─ 배송지 변경 Action 연결
```

### Current

```text
Orchestrator
↓
delivery_address_flow
├─ 최초 요청 처리
├─ 주문 선택
├─ 새 주소 수집
├─ 최종 승인
└─ Service / State 연결
```

기존 Orchestrator에 남아 있던 배송지 변경 응답 함수와 관련 unused import도 제거하였다.

배송지 변경 관련 테스트 9개를 통과한 뒤 전체 Regression Test를 수행하여 기존 기능이 유지되는 것을 확인하였다.

```text
144 passed
```

---

## 2-5. 주문 취소 Flow 분리

두 번째로 주문 취소 기능을 `order_cancel_flow.py`로 분리하였다.

이동한 Pending Action은 다음 두 개이다.

```text
order_cancel_selection
confirm_cancel
```

주문 취소는 Refund와 연결되는 기능이므로, Optimization 1에서 정리한 Refund Service 책임 구조를 그대로 유지하였다.

### Current

```text
Orchestrator
↓
order_cancel_flow
├─ 최초 요청 처리
├─ 주문 선택
├─ 사용자 최종 승인
├─ Refund 사전 검증
├─ 주문 / 결제 취소 Action
└─ Refund Service 연결
```

계좌이체 환불 과정에서 사용하는

```text
collect_refund_account
```

는 주문 취소 전용 State가 아니므로 `order_cancel_flow.py` 내부로 이동하지 않았다.

주문 취소 Flow는 필요한 Refund Context만 State에 저장한 뒤 공통 Refund 처리 단계로 연결하도록 유지하였다.

주문 취소 및 Refund 관련 Target Test는 다음과 같이 통과하였다.

```text
24 passed
```

이후 전체 Regression Test에서도 기존 기능이 유지되었다.

```text
144 passed
```

---

## 2-6. 현재 정량 비교

현재까지의 구조 변경 결과는 다음과 같다.

| 측정 항목                          |     Before |    Current |     변화 |
| ------------------------------ | ---------: | ---------: | -----: |
| `orchestrator.py` Line 수       |      2,707 |      1,945 | 762 감소 |
| Orchestrator 직접 Pending Action |         13 |          8 |   5 감소 |
| 전체 Regression Test             | 144 passed | 144 passed |  기능 유지 |

비율로 보면 다음과 같다.

```text
orchestrator.py Line 수
2,707 → 1,945
약 28.1% 감소

Orchestrator 직접 Pending Action
13 → 8
약 38.5% 감소
```

단, 762 Line 감소 전체를 Feature Flow 분리만의 효과로 해석하지 않는다.

이번 과정에서는 함께 발견된

```text
unreachable dead code
중복 Response Builder
unused import
```

도 정리하였다.

따라서 Line 수 감소는 **Orchestrator Structure Optimization 과정 전체의 변화**로 기록한다.

이번 최적화에서 더 중요한 구조 지표는 Orchestrator가 직접 처리해야 하는 Pending Action이

```text
13개 → 8개
```

로 감소했다는 점이다.

---

## 2-7. 현재 구조

현재 구조는 다음과 같다.

```text
User Request
      ↓
  Orchestrator
      ↓
Feature 선택
      │
      ├─ delivery_address_flow
      │    └─ Service / State
      │
      ├─ order_cancel_flow
      │    └─ Service / Refund Service / State
      │
      └─ 아직 중앙에서 처리하는 기존 기능
```

배송지 변경과 주문 취소의 상세 Multi-turn 흐름은 각 Feature Flow가 담당하고, Orchestrator는 해당 Flow를 선택하여 호출하는 구조로 변경되었다.

현재까지 전체 Regression Test는

```text
144 passed
0 failed
```

를 유지하고 있다.

따라서 현재 단계에서는 **기존 기능과 Write Action 안전 절차를 유지하면서 중앙 Orchestrator의 기능별 세부 처리 책임을 Feature Flow로 분리한 것**을 주요 개선 결과로 본다.
