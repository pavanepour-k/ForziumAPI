use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};
use forzium::dependencies::{Dependency, DependencyResolver, DependencyScope};
use forzium::response::{create_response, serialize_json_response, ResponseBody};
use forzium::routing::{parse_route_pattern, HttpMethod, RouteMatcher};
use forzium::validation::{validate_buffer_size, validate_utf8_string};
use serde_json::json;
use std::time::Duration;

fn benchmark_buffer_validation(c: &mut Criterion) {
    let mut group = c.benchmark_group("buffer_validation");
    group.measurement_time(Duration::from_secs(10));

    // Test different buffer sizes
    for size in [10, 100, 1000, 10000, 100000].iter() {
        let data = vec![b'x'; *size];

        group.bench_with_input(
            BenchmarkId::new("validate_buffer", size),
            &data,
            |b, data| {
                b.iter(|| {
                    let result = validate_buffer_size(black_box(data));
                    black_box(result)
                });
            },
        );
    }

    group.finish();
}

fn benchmark_utf8_validation(c: &mut Criterion) {
    let mut group = c.benchmark_group("utf8_validation");

    // ASCII data
    let ascii_data = "Hello, World!".repeat(100).into_bytes();
    group.bench_function("validate_utf8_ascii", |b| {
        b.iter(|| {
            let result = validate_utf8_string(black_box(&ascii_data));
            black_box(result)
        });
    });

    // Unicode data
    let unicode_data = "Hello, こんにちは 🌍".repeat(50).into_bytes();
    group.bench_function("validate_utf8_unicode", |b| {
        b.iter(|| {
            let result = validate_utf8_string(black_box(&unicode_data));
            black_box(result)
        });
    });

    group.finish();
}

fn benchmark_routing(c: &mut Criterion) {
    let mut group = c.benchmark_group("routing");

    // Setup router with various routes
    let mut matcher = RouteMatcher::new();

    // Add routes
    for i in 0..100 {
        let route = parse_route_pattern(
            &format!("/api/v1/users/{}/posts/{}", "{user_id}", "{post_id}"),
            "GET",
            &format!("handler_{}", i),
        )
        .unwrap();
        matcher.add_route(route);
    }

    // Benchmark route matching
    group.bench_function("match_route_simple", |b| {
        b.iter(|| {
            let result = matcher.match_route(
                black_box("/api/v1/users/123/posts/456"),
                black_box(&HttpMethod::GET),
            );
            black_box(result)
        });
    });

    // Benchmark route parsing
    group.bench_function("parse_route_pattern", |b| {
        b.iter(|| {
            let result = parse_route_pattern(
                black_box("/api/v1/items/{item_id}/details"),
                black_box("POST"),
                black_box("item_handler"),
            );
            black_box(result)
        });
    });

    group.finish();
}

fn benchmark_dependencies(c: &mut Criterion) {
    let mut group = c.benchmark_group("dependencies");

    // Setup dependency resolver
    let mut resolver = DependencyResolver::new();

    // Register dependencies
    for i in 0..50 {
        let dep = Dependency {
            key: format!("service_{}", i),
            scope: if i % 3 == 0 {
                DependencyScope::Singleton
            } else if i % 3 == 1 {
                DependencyScope::Request
            } else {
                DependencyScope::Transient
            },
            factory: Box::new(move || Box::new(format!("instance_{}", i))),
        };
        resolver.register(dep);
    }

    // Benchmark singleton resolution (should be cached)
    group.bench_function("resolve_singleton", |b| {
        b.iter(|| {
            let result = resolver.resolve(black_box("service_0"));
            black_box(result)
        });
    });

    // Benchmark transient resolution (new instance each time)
    group.bench_function("resolve_transient", |b| {
        b.iter(|| {
            let result = resolver.resolve(black_box("service_2"));
            black_box(result)
        });
    });

    group.finish();
}

fn benchmark_response_serialization(c: &mut Criterion) {
    let mut group = c.benchmark_group("response_serialization");

    // Small JSON response
    let small_json = json!({
        "status": "ok",
        "data": {"id": 123, "name": "test"}
    });

    group.bench_function("serialize_json_small", |b| {
        b.iter(|| {
            let bytes = serialize_json_response(black_box(&small_json));
            black_box(bytes)
        });
    });

    // Large JSON response
    let mut items = Vec::new();
    for i in 0..1000 {
        items.push(json!({
            "id": i,
            "name": format!("Item {}", i),
            "tags": vec!["tag1", "tag2", "tag3"],
            "metadata": {
                "created": "2024-01-01T00:00:00Z",
                "updated": "2024-01-01T00:00:00Z"
            }
        }));
    }
    let large_json = json!({"items": items});

    group.bench_function("serialize_json_large", |b| {
        b.iter(|| {
            let bytes = serialize_json_response(black_box(&large_json));
            black_box(bytes)
        });
    });

    // Response creation
    group.bench_function("create_response", |b| {
        b.iter(|| {
            let response = create_response(
                black_box(200),
                black_box(ResponseBody::Json(small_json.clone())),
            );
            black_box(response)
        });
    });

    group.finish();
}

// FFI-specific benchmarks (requires Python environment)
#[cfg(feature = "python-testing")]
fn benchmark_ffi_overhead(c: &mut Criterion) {
    use pyo3::prelude::*;

    let mut group = c.benchmark_group("ffi_overhead");
    group.measurement_time(Duration::from_secs(20));

    Python::with_gil(|py| {
        // Import our module
        let module = py.import("forzium._rust_lib").unwrap();

        // Minimal FFI call - validate_buffer_size
        let small_data = vec![0u8; 100];
        group.bench_function("ffi_validate_buffer_minimal", |b| {
            b.iter(|| {
                let result = module.call_method1("validate_buffer_size", (black_box(&small_data),));
                black_box(result)
            });
        });

        // String conversion FFI call
        let utf8_data = "Hello, World!".as_bytes();
        group.bench_function("ffi_validate_utf8", |b| {
            b.iter(|| {
                let result = module.call_method1("validate_utf8_string", (black_box(utf8_data),));
                black_box(result)
            });
        });

        // Complex object FFI call - PyRouteMatcher
        let matcher_class = module.getattr("PyRouteMatcher").unwrap();
        let matcher = matcher_class.call0().unwrap();

        group.bench_function("ffi_route_match", |b| {
            // Add a route first
            matcher
                .call_method1("add_route", ("/test/{id}", "GET", "test_handler"))
                .unwrap();

            b.iter(|| {
                let result =
                    matcher.call_method1("match_path", (black_box("/test/123"), black_box("GET")));
                black_box(result)
            });
        });
    });

    group.finish();
}

// Main benchmark groups
criterion_group!(
    benches,
    benchmark_buffer_validation,
    benchmark_utf8_validation,
    benchmark_routing,
    benchmark_dependencies,
    benchmark_response_serialization
);

// Add FFI benchmarks only when Python feature is enabled
#[cfg(feature = "python-testing")]
criterion_group!(ffi_benches, benchmark_ffi_overhead);

#[cfg(not(feature = "python-testing"))]
criterion_main!(benches);

#[cfg(feature = "python-testing")]
criterion_main!(benches, ffi_benches);
