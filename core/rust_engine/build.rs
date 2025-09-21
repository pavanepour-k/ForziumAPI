fn main() {
    // Query PyO3's build configuration to obtain interpreter paths and
    // link information for the embedding build. Without explicitly linking
    // against the Python runtime, `cargo test` fails with unresolved symbols
    // for core `Py*` APIs. The build script therefore emits both search and
    // link directives so that unit tests and binaries can locate libpython
    // at compile and run time.
    let cfg = pyo3_build_config::get();

    if std::env::var("FORZIUM_LINK_LIBPYTHON").is_ok() {
        if let Some(lib_dir) = &cfg.lib_dir {
            // Embed the Python library path so binaries can locate libpython even
            // when it is absent from the system's default search locations.
            println!("cargo:rustc-link-arg=-Wl,-rpath,{}", lib_dir);
            println!("cargo:rustc-link-search=native={}", lib_dir);
        }

        // PyO3 may not report a library name when building with the stable ABI.
        // Fallback to the canonical CPython shared library on Linux.
        let lib_name = cfg
            .lib_name
            .clone()
            .unwrap_or_else(|| "python3.12".to_string());
        println!("cargo:rustc-link-lib={}", lib_name);
    }
}
