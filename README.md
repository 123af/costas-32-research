# Costas-32 Research

이 저장소는 차수 32 코스타스 배열의 존재 또는 비존재 연구를 위한 저장소다.

## 배열 표현

길이 n의 순열

[p_1, p_2, ..., p_n]

은 점 집합

(1,p_1), (2,p_2), ..., (n,p_n)

을 나타낸다.

인덱스와 순열 값은 모두 1부터 시작한다.

## 검증기

기준 검증기:

verifier/reference_verifier.py

독립 검증기:

verifier/independent_verifier.py

자가시험:

python verifier/reference_verifier.py --self-test
python verifier/independent_verifier.py --self-test

후보 검증:

python verifier/reference_verifier.py \
  --permutation "[1,2,4,3]" \
  --output json

모든 후보는 두 검증기를 모두 통과해야 한다.

## 중요 규칙

- 휴리스틱 실패는 비존재 증명이 아니다.
- 계산을 실제로 실행하지 않았다면 검증됐다고 기록하지 않는다.
- 연구 에이전트는 자신의 결과를 proved 또는 verified로 선언하지 않는다.
- 후보 배열에는 순열 전체와 검증 결과를 함께 기록한다.
