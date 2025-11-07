"""
Benchmark suite for comparing Python and Rust implementation performance.

This module provides benchmarking tools to measure and compare the performance
of equivalent operations in pure Python versus Rust implementations.
"""

import time
import numpy as np
import argparse
import json
from pathlib import Path
from typing import Callable, Dict, Any, List, TypedDict
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor


class BenchmarkResult(TypedDict):
    """Typed dictionary for benchmark results."""
    
    name: str
    python_time: float
    rust_time: float
    speedup: float
    size: int | tuple[int, ...]
    threads: int
    notes: str


def time_execution(func: Callable[..., Any], *args: Any, **kwargs: Any) -> float:
    """
    Measure execution time of a function.
    
    Args:
        func: Function to benchmark
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Execution time in seconds
    """
    start_time = time.perf_counter()
    func(*args, **kwargs)
    return time.perf_counter() - start_time


def benchmark_matrix_multiply(size: int, runs: int = 5) -> BenchmarkResult:
    """
    Benchmark matrix multiplication in Python vs. Rust.
    
    Args:
        size: Size of the square matrix to test
        runs: Number of runs to average
        
    Returns:
        Dictionary with benchmark results
    """
    # Import implementations
    try:
        import forzium_engine
        from forzium._ffi.zero_copy import matrix_multiply_inplace
    except ImportError:
        raise ImportError("Rust engine not available. Make sure forzium_engine is built.")
    
    # Create test data
    matrix = np.random.random((size, size))
    matrix_list = matrix.tolist()
    factor = 2.0
    
    # Define Python implementation
    def py_multiply(m: List[List[float]], f: float) -> List[List[float]]:
        return [[x * f for x in row] for row in m]
    
    # Define NumPy implementation
    def numpy_multiply(m: np.ndarray, f: float) -> np.ndarray:
        return m * f
    
    # Define Rust implementation
    def rust_multiply(m: List[List[float]], f: float) -> List[List[float]]:
        return forzium_engine.multiply(m, f)
    
    # Define zero-copy implementation
    def zero_copy_multiply_bench(m: np.ndarray, f: float) -> np.ndarray:
        return matrix_multiply_inplace(m, f)
    
    # Run benchmarks
    py_times = []
    rust_times = []
    numpy_times = []
    zero_copy_times = []
    
    for _ in range(runs):
        # Deep copy to avoid modification between runs
        matrix_copy = [row[:] for row in matrix_list]
        py_times.append(time_execution(py_multiply, matrix_copy, factor))
        
        matrix_copy = [row[:] for row in matrix_list]
        rust_times.append(time_execution(rust_multiply, matrix_copy, factor))
        
        matrix_np_copy = matrix.copy()
        numpy_times.append(time_execution(numpy_multiply, matrix_np_copy, factor))
        
        matrix_np_copy = matrix.copy()
        zero_copy_times.append(time_execution(zero_copy_multiply_bench, matrix_np_copy, factor))
    
    # Calculate averages
    avg_py = sum(py_times) / runs
    avg_rust = sum(rust_times) / runs
    avg_numpy = sum(numpy_times) / runs
    avg_zero_copy = sum(zero_copy_times) / runs
    
    # Calculate speedups
    rust_speedup = avg_py / avg_rust if avg_rust > 0 else 0
    numpy_speedup = avg_py / avg_numpy if avg_numpy > 0 else 0
    zero_copy_speedup = avg_py / avg_zero_copy if avg_zero_copy > 0 else 0
    
    return {
        "name": "matrix_multiply",
        "python_time": avg_py,
        "rust_time": avg_rust,
        "numpy_time": avg_numpy,
        "zero_copy_time": avg_zero_copy,
        "rust_speedup": rust_speedup,
        "numpy_speedup": numpy_speedup,
        "zero_copy_speedup": zero_copy_speedup,
        "size": size,
        "threads": 1,
        "notes": f"Matrix size: {size}x{size}"
    }


def benchmark_convolution(size: int, kernel_size: int = 3, runs: int = 5) -> BenchmarkResult:
    """
    Benchmark convolution operation in Python vs. Rust.
    
    Args:
        size: Size of the square input matrix
        kernel_size: Size of the square convolution kernel
        runs: Number of runs to average
        
    Returns:
        Dictionary with benchmark results
    """
    # Import implementations
    try:
        import forzium_engine
        from forzium._ffi.zero_copy import convolve2d
    except ImportError:
        raise ImportError("Rust engine not available. Make sure forzium_engine is built.")
    
    # Create test data
    image = np.random.random((size, size))
    kernel = np.random.random((kernel_size, kernel_size))
    image_list = image.tolist()
    kernel_list = kernel.tolist()
    
    # Define Python implementation
    def py_convolve(img: List[List[float]], k: List[List[float]]) -> List[List[float]]:
        out_rows = len(img) - len(k) + 1
        out_cols = len(img[0]) - len(k[0]) + 1
        result = [[0.0 for _ in range(out_cols)] for _ in range(out_rows)]
        
        for i in range(out_rows):
            for j in range(out_cols):
                for ki in range(len(k)):
                    for kj in range(len(k[0])):
                        result[i][j] += img[i + ki][j + kj] * k[ki][kj]
        
        return result
    
    # Define NumPy implementation
    def numpy_convolve(img: np.ndarray, k: np.ndarray) -> np.ndarray:
        from scipy import signal
        return signal.convolve2d(img, k, mode='valid')
    
    # Define Rust implementation
    def rust_convolve(img: List[List[float]], k: List[List[float]]) -> List[List[float]]:
        return forzium_engine.conv2d(img, k)
    
    # Define zero-copy implementation
    def zero_copy_convolve(img: np.ndarray, k: np.ndarray) -> np.ndarray:
        return convolve2d(img, k)
    
    # Run benchmarks
    py_times = []
    rust_times = []
    numpy_times = []
    zero_copy_times = []
    
    for _ in range(runs):
        py_times.append(time_execution(py_convolve, image_list, kernel_list))
        rust_times.append(time_execution(rust_convolve, image_list, kernel_list))
        
        try:
            numpy_times.append(time_execution(numpy_convolve, image, kernel))
        except ImportError:
            numpy_times.append(0)  # scipy might not be available
            
        zero_copy_times.append(time_execution(zero_copy_convolve, image, kernel))
    
    # Calculate averages
    avg_py = sum(py_times) / runs
    avg_rust = sum(rust_times) / runs
    avg_numpy = sum(numpy_times) / runs if numpy_times[0] > 0 else 0
    avg_zero_copy = sum(zero_copy_times) / runs
    
    # Calculate speedups
    rust_speedup = avg_py / avg_rust if avg_rust > 0 else 0
    numpy_speedup = avg_py / avg_numpy if avg_numpy > 0 else 0
    zero_copy_speedup = avg_py / avg_zero_copy if avg_zero_copy > 0 else 0
    
    return {
        "name": "convolution",
        "python_time": avg_py,
        "rust_time": avg_rust,
        "numpy_time": avg_numpy,
        "zero_copy_time": avg_zero_copy,
        "rust_speedup": rust_speedup,
        "numpy_speedup": numpy_speedup,
        "zero_copy_speedup": zero_copy_speedup,
        "size": (size, size, kernel_size, kernel_size),
        "threads": 1,
        "notes": f"Image size: {size}x{size}, Kernel: {kernel_size}x{kernel_size}"
    }


def benchmark_matrix_operations_parallel(size: int, runs: int = 3) -> BenchmarkResult:
    """
    Benchmark parallel matrix operations in Python vs. Rust.
    
    Args:
        size: Size of the square matrix
        runs: Number of runs to average
        
    Returns:
        Dictionary with benchmark results
    """
    # Import implementations
    try:
        import forzium_engine
    except ImportError:
        raise ImportError("Rust engine not available. Make sure forzium_engine is built.")
    
    # Optimize thread pools
    forzium_engine.optimize_thread_pools()
    
    # Create test data
    matrix_a = np.random.random((size, size)).tolist()
    matrix_b = np.random.random((size, size)).tolist()
    
    # Define Python implementation with manual threading
    def py_parallel_matmul(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
        def compute_row(row_idx: int) -> List[float]:
            result_row = []
            for j in range(len(b[0])):
                val = 0.0
                for k in range(len(b)):
                    val += a[row_idx][k] * b[k][j]
                result_row.append(val)
            return result_row
        
        with ThreadPoolExecutor() as executor:
            result = list(executor.map(compute_row, range(len(a))))
        return result
    
    # Define Rust implementation
    def rust_matmul(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
        return forzium_engine.simd_matmul(a, b)
    
    # Run benchmarks
    py_times = []
    rust_times = []
    
    for _ in range(runs):
        py_times.append(time_execution(py_parallel_matmul, matrix_a, matrix_b))
        rust_times.append(time_execution(rust_matmul, matrix_a, matrix_b))
    
    # Calculate averages
    avg_py = sum(py_times) / runs
    avg_rust = sum(rust_times) / runs
    
    # Get thread pool metrics
    metrics = forzium_engine.rayon_pool_metrics()
    threads_used = metrics["observed_threads"]
    
    # Calculate speedup
    speedup = avg_py / avg_rust if avg_rust > 0 else 0
    
    return {
        "name": "parallel_matmul",
        "python_time": avg_py,
        "rust_time": avg_rust,
        "speedup": speedup,
        "size": size,
        "threads": threads_used,
        "notes": f"Matrix size: {size}x{size}, Rayon threads: {threads_used}"
    }


def run_all_benchmarks(save_path: str | None = None) -> List[Dict[str, Any]]:
    """
    Run all benchmarks and optionally save results to a file.
    
    Args:
        save_path: Optional path to save the benchmark results as JSON
        
    Returns:
        List of benchmark result dictionaries
    """
    print("Running benchmarks...")
    results = []
    
    # Matrix multiplication benchmarks
    for size in [100, 500, 1000]:
        print(f"Benchmarking matrix multiply ({size}x{size})...")
        result = benchmark_matrix_multiply(size)
        results.append(result)
        print(f"  Python: {result['python_time']:.6f}s")
        print(f"  Rust: {result['rust_time']:.6f}s")
        print(f"  NumPy: {result['numpy_time']:.6f}s")
        print(f"  Zero-copy: {result['zero_copy_time']:.6f}s")
        print(f"  Rust speedup: {result['rust_speedup']:.2f}x")
        print(f"  Zero-copy speedup: {result['zero_copy_speedup']:.2f}x")
    
    # Convolution benchmarks
    for size in [50, 100, 200]:
        print(f"Benchmarking convolution ({size}x{size})...")
        result = benchmark_convolution(size)
        results.append(result)
        print(f"  Python: {result['python_time']:.6f}s")
        print(f"  Rust: {result['rust_time']:.6f}s")
        print(f"  NumPy: {result['numpy_time']:.6f}s")
        print(f"  Zero-copy: {result['zero_copy_time']:.6f}s")
        print(f"  Rust speedup: {result['rust_speedup']:.2f}x")
        print(f"  Zero-copy speedup: {result['zero_copy_speedup']:.2f}x")
    
    # Parallel operations benchmarks
    for size in [500, 1000]:
        print(f"Benchmarking parallel operations ({size}x{size})...")
        result = benchmark_matrix_operations_parallel(size)
        results.append(result)
        print(f"  Python+Threads: {result['python_time']:.6f}s")
        print(f"  Rust+Rayon: {result['rust_time']:.6f}s")
        print(f"  Speedup: {result['speedup']:.2f}x")
        print(f"  Threads used: {result['threads']}")
    
    if save_path:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {save_path}")
    
    return results


def visualize_results(results: List[Dict[str, Any]], save_path: str | None = None) -> None:
    """
    Create visualizations of benchmark results.
    
    Args:
        results: List of benchmark result dictionaries
        save_path: Optional path to save the visualization
    """
    # Group results by benchmark type
    matrix_multiply = [r for r in results if r["name"] == "matrix_multiply"]
    convolution = [r for r in results if r["name"] == "convolution"]
    parallel = [r for r in results if r["name"] == "parallel_matmul"]
    
    # Create figure with subplots
    fig, axes = plt.subplots(3, 1, figsize=(12, 15))
    
    # Plot matrix multiplication results
    if matrix_multiply:
        sizes = [r["size"] for r in matrix_multiply]
        python_times = [r["python_time"] for r in matrix_multiply]
        rust_times = [r["rust_time"] for r in matrix_multiply]
        numpy_times = [r["numpy_time"] for r in matrix_multiply]
        zero_copy_times = [r["zero_copy_time"] for r in matrix_multiply]
        
        axes[0].bar(range(len(sizes)), python_times, width=0.2, label="Python")
        axes[0].bar([x + 0.2 for x in range(len(sizes))], rust_times, width=0.2, label="Rust")
        axes[0].bar([x + 0.4 for x in range(len(sizes))], numpy_times, width=0.2, label="NumPy")
        axes[0].bar([x + 0.6 for x in range(len(sizes))], zero_copy_times, width=0.2, label="Zero-copy")
        
        axes[0].set_xticks([x + 0.3 for x in range(len(sizes))])
        axes[0].set_xticklabels([f"{s}x{s}" for s in sizes])
        axes[0].set_ylabel("Time (seconds)")
        axes[0].set_title("Matrix Multiplication Performance")
        axes[0].legend()
        
        # Add speedup annotations
        for i, r in enumerate(matrix_multiply):
            axes[0].annotate(
                f"{r['rust_speedup']:.1f}x",
                xy=(i + 0.2, rust_times[i]),
                xytext=(0, 10),
                textcoords="offset points",
                ha='center'
            )
            axes[0].annotate(
                f"{r['zero_copy_speedup']:.1f}x",
                xy=(i + 0.6, zero_copy_times[i]),
                xytext=(0, 10),
                textcoords="offset points",
                ha='center'
            )
    
    # Plot convolution results
    if convolution:
        sizes = [r["size"][0] for r in convolution]
        python_times = [r["python_time"] for r in convolution]
        rust_times = [r["rust_time"] for r in convolution]
        numpy_times = [r["numpy_time"] for r in convolution]
        zero_copy_times = [r["zero_copy_time"] for r in convolution]
        
        axes[1].bar(range(len(sizes)), python_times, width=0.2, label="Python")
        axes[1].bar([x + 0.2 for x in range(len(sizes))], rust_times, width=0.2, label="Rust")
        axes[1].bar([x + 0.4 for x in range(len(sizes))], numpy_times, width=0.2, label="NumPy/SciPy")
        axes[1].bar([x + 0.6 for x in range(len(sizes))], zero_copy_times, width=0.2, label="Zero-copy")
        
        axes[1].set_xticks([x + 0.3 for x in range(len(sizes))])
        axes[1].set_xticklabels([f"{s}x{s}" for s in sizes])
        axes[1].set_ylabel("Time (seconds)")
        axes[1].set_title("Convolution Operation Performance")
        axes[1].legend()
        
        # Add speedup annotations
        for i, r in enumerate(convolution):
            axes[1].annotate(
                f"{r['rust_speedup']:.1f}x",
                xy=(i + 0.2, rust_times[i]),
                xytext=(0, 10),
                textcoords="offset points",
                ha='center'
            )
            axes[1].annotate(
                f"{r['zero_copy_speedup']:.1f}x",
                xy=(i + 0.6, zero_copy_times[i]),
                xytext=(0, 10),
                textcoords="offset points",
                ha='center'
            )
    
    # Plot parallel operation results
    if parallel:
        sizes = [r["size"] for r in parallel]
        python_times = [r["python_time"] for r in parallel]
        rust_times = [r["rust_time"] for r in parallel]
        speedups = [r["speedup"] for r in parallel]
        threads = [r["threads"] for r in parallel]
        
        axes[2].bar(range(len(sizes)), python_times, width=0.4, label="Python+Threads")
        axes[2].bar([x + 0.4 for x in range(len(sizes))], rust_times, width=0.4, label="Rust+Rayon")
        
        axes[2].set_xticks([x + 0.2 for x in range(len(sizes))])
        axes[2].set_xticklabels([f"{s}x{s}\n({t} threads)" for s, t in zip(sizes, threads)])
        axes[2].set_ylabel("Time (seconds)")
        axes[2].set_title("Parallel Matrix Operations Performance")
        axes[2].legend()
        
        # Add speedup annotations
        for i, speedup in enumerate(speedups):
            axes[2].annotate(
                f"{speedup:.1f}x",
                xy=(i + 0.4, rust_times[i]),
                xytext=(0, 10),
                textcoords="offset points",
                ha='center'
            )
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path)
        print(f"Visualization saved to {save_path}")
    else:
        plt.show()


def main() -> None:
    """Execute the benchmark suite."""
    parser = argparse.ArgumentParser(description="ForziumAPI Rust vs. Python benchmarks")
    parser.add_argument(
        "--save", 
        help="Path to save benchmark results as JSON",
        default="metrics/benchmark_results.json"
    )
    parser.add_argument(
        "--visualize", 
        help="Path to save visualization",
        default="metrics/benchmark_visualization.png"
    )
    args = parser.parse_args()
    
    # Run benchmarks
    results = run_all_benchmarks(args.save)
    
    # Create visualization
    visualize_results(results, args.visualize)


if __name__ == "__main__":
    main()
