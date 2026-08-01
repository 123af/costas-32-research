# Verifier

이 폴더에는 코스타스 배열 후보를 검사하는 프로그램을 보관한다.

예정 파일:

- `reference_verifier.py`: 단순한 기준 검증기
- `independent_verifier.py`: 다른 알고리즘을 사용하는 독립 검증기
- `test_verifiers.py`: 두 검증기의 테스트
- `test_cases.json`: 유효·무효 테스트 사례

모든 후보는 두 독립 검증기의 결과가 일치해야 한다.

검증기를 실행하지 못한 경우 후보를 verified로 표시하지 않는다.
