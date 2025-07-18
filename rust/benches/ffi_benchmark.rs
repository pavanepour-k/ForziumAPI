use criterion::{black_box, criterion_group, criterion_main, Criterion};
use forzium::validation::{validate_buffer_size, validate_utf8_string};

fn benchmark_buffer_validation(c: &mut Criterion) {
    let data = vec![b'x'; 1000];

    c.bench_function("validate_buffer_1kb", |b| {
        b.iter(|| validate_buffer_size(black_box(&data)))
    });
}

fn benchmark_utf8_validation(c: &mut Criterion) {
    let data = "Hello, 世界!".repeat(100).into_bytes();

    c.bench_function("validate_utf8_unicode", |b| {
        b.iter(|| validate_utf8_string(black_box(&data)))
    });
}

criterion_group!(
    benches,
    benchmark_buffer_validation,
    benchmark_utf8_validation
);
criterion_main!(benches);
