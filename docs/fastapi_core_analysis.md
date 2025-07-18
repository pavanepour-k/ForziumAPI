```
Root/
├── rust/
│   ├── core/         # 순수 Rust 로직
│   ├── bindings/     # PyO3 기반 FFI
│   └── pkg/          # maturin + pyproject.toml 기반 Python 패키징
├── forzium/          # Python 패키지 루트
│   ├── __init__.py
│   ├── *.pyi
│   ├── _ffi/
│   ├── routing/
│   ├── dependencies/
│   ├── request/
│   ├── response/
│   ├── validation/
│   ├── core/
│   ├── exceptions/
│   └── validators.py
│   └── tests/
│       ├── unit/
│       │   ├── test_dependencies.py      🔧 FIX
│       │   ├── test_routing.py           ✅ KEEP
│       │   ├── test_validators.py        ✅ KEEP
│       │   └── test_ffi_safety.py        🔧 CREATE
│       ├── integration/
│       │   ├── test_full_cycle.py        🔧 FIX
│       │   ├── test_memory_safety.py     🔧 CREATE
│       │   └── test_error_propagation.py 🔧 CREATE
│       └── benchmarks/
│           ├── test_ffi_overhead.py      🔧 FIX
│           └── test_memory_usage.py      🔧 CREATE
└── Makefile                              🔧 UPDATE
```

```




E:.
├── .gitignore
├── LICENSE
├── README.md
├── pyproject.toml                # (선택) 전체 프로젝트용 pyproject
│
├── .github/
│   └── workflows/
│       ├── ci-python.yml         # Python 테스트 및 린팅
│       ├── ci-rust.yml           # Rust 빌드 및 테스트
│       └── ci-intergration.yml    # Rust ↔ Python 통합 테스트
│
├── docs/
│   └── fastapi_core_analysis.md
│
├── python/
│   ├── pyproject.toml            # Python wheel 패키지용 (maturin 사용)
│   ├── README.md
│   ├── Makefile
│   ├── .pre-commit-config.yaml
│   ├── src/
│   │   └── forzium/
│   │       ├── api/
│   │       ├── core/
│   │       ├── services/
│   │       ├── ...               # 기타 패키지
│   │       └── ext/              # 기존 _rust → 명확한 명칭 (예: ext/native)
│   │           ├── __init__.py
│   │           ├── dependencies.py
│   │           └── response.py
│   └── tests/
│       ├── unit/
│       ├── integration/          # 기존 intergration → 오타 수정
│       └── benchmarks/
│
├── rust/
│   ├── Cargo.toml                # (선택) workspace 구성 가능
│   ├── rust-toolchain.toml
│   ├── .cargo/
│   │   └── config.toml
│   ├── bindings/                # PyO3 + maturin 연동용 crate
│   │   ├── Cargo.toml
│   │   ├── pyproject.toml        # Python 빌드 설정
│   │   └── src/
│   │       └── lib.rs            # #[pymodule] 진입점
│   ├── core/                    # 순수 Rust 로직 (비-PyO3)
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── api.rs
│   │       ├── response/
│   │       ├── routing/
│   │       └── ...
│   └── tests/
│       └── integration_test.rs
│
├── shared/                      # 기존 share → 공유 리소스 폴더
│   ├── constants/
│   │   └── limit.json
│   ├── proto/
│   │   └── ValidationService.proto
│   └── schemas/
│       └── validation.json



```