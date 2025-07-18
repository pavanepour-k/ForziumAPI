**Rules for `core/`:**
- Focused on `pub fn`, `struct`, `enum`, `trait`  
- Tests must be separated into `tests/`  
- External interfaces are explicitly exposed via `pub use`  
- Role: Logic  
- Includes: Pure Rust code  
- Allowed dependencies: None  
- Testing tool: `cargo test` — unit/integration tests  

**Rules for `bindings/`:**
- Each Rust module only includes PyO3 wrapper functions that call the `core/` public API  
- `lib.rs` is the PyO3 entrypoint  
- Only imports required functionality via `use forzium_core::*`  
- Uses `GIL`, `PyResult`, `wrap_pyfunction!`, etc., only here  
- Role: Interface  
- Includes: PyO3, GIL, public wrappers  
- Allowed dependencies: `core/`  
- Testing tool: `pytest` + `maturin develop` — calling bindings from Python  

**Rules for `pkg/`:**
- In `pyproject.toml`’s `[tool.maturin]`, `bindings = "../bindings"`  
- Only involved in Python wheel building  
- Determines the Python import module name (`module-name = forzium`)  
- Role: Packaging  
- Includes: wheel metadata, stub module  
- Allowed dependencies: `bindings/`  
- Testing tool: `pytest` after wheel installation — final smoke tests before release  

---

## Naming Conventions

**Rust logic crate**  
- `forzium_core`: Pure Rust logic (`core/`)  

**PyO3 binding crate**  
- `forzium_ffi`: Binding layer linking to Python (`bindings/`)  

**Python native module (shared library)**  
- `forzium._ffi`: The `.so`/`.pyd` module imported in Python  

**Python package root**  
- `forzium`: User‑facing Python package (`forzium/`)  

**Wheel module name at maturin build time**  
- `forzium._ffi`: The name under which the PyO3 module is provided in the wheel (`module-name`)  

**Python wheel project name (`pyproject.toml`)**  
- `forzium`: The name for `pip install forzium` (`project.name`)  

---

```plaintext

Project-Root (Rust)
├── core/
│   ├── src/
│   │   ├── lib.rs                # re-export modules via pub use
│   │   ├── api.rs                # internal use only
│   │   ├── errors.rs
│   │   ├── types.rs
│   │   ├── dependencies/
│   │   ├── request/
│   │   ├── response/
│   │   ├── routing/
│   │   └── validation/
│   ├── tests/
│   └── Cargo.toml
│
├── bindings/
│   ├── src/
│   │   ├── lib.rs                # defines #[pymodule]
│   │   ├── dependencies.rs
│   │   ├── request.rs
│   │   ├── response.rs
│   │   ├── routing.rs            # #[pyfunction] fn py_validate(...)
│   │   └── validation.rs
│   └── Cargo.toml
│
├── pkg/...
│
└── benches/
    └── ffi_benchmark.rs

```


```plaintext

Project-Root (Python)
├── forzium/
│   ├── __init__.py             # top‑level API entry point
│   ├── _ffi/                   # Rust PyO3 binding wrappers
│   │   ├── __init__.py
│   │   ├── validation.py       # wraps calls like `from forzium._ffi import py_validate`
│   │   ├── routing.py
│   │   └── ...                 # wraps the target binding modules
│   ├── core/                   # core Python logic modules (business rules)
│   │   └── ...
│   ├── routing/                # domain‑based routing logic
│   │   └── ...
│   ├── dependencies/           # DI, configuration object definitions, etc.
│   │   └── ...
│   ├── request/                # request handling logic
│   │   └── ...
│   ├── response/               # response transformation logic
│   │   └── ...
│   ├── validation/             # validation logic (Python)
│   │   └── ...
│   ├── exceptions/             # common exception definitions
│   │   └── ...
│   ├── validators.py           # high‑level validation utilities
│   ├── *.pyi                   # stub files for type hints (Rust functions, etc.)

```