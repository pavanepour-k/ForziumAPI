import importlib
import sys

import importlib
import sys

from core.service import gpu


def reload_gpu() -> None:
    importlib.reload(gpu)


def test_cpu_fallback(monkeypatch) -> None:
    monkeypatch.delenv("FORZIUM_USE_GPU", raising=False)
    monkeypatch.delitem(sys.modules, "cupy", raising=False)
    reload_gpu()
    result = gpu.elementwise_add([[1.0, 2.0]], [[3.0, 4.0]])
    assert result == [[4.0, 6.0]]
    assert gpu.USE_GPU is False


def test_gpu_enabled(monkeypatch) -> None:
    monkeypatch.setenv("FORZIUM_USE_GPU", "1")

    class FakeArray(list):
        def __add__(self, other):
            return FakeArray(
                [[x + y for x, y in zip(r1, r2)] for r1, r2 in zip(self, other)]
            )

        def tolist(self):  # type: ignore[override]
            return list(self)

    class FakeCupy:
        used = False

        def array(self, data):
            FakeCupy.used = True
            return FakeArray(data)

        def asnumpy(self, arr):
            return arr

    monkeypatch.setitem(sys.modules, "cupy", FakeCupy())
    reload_gpu()
    result = gpu.elementwise_add([[1.0, 2.0]], [[3.0, 4.0]])
    assert result == [[4.0, 6.0]]
    assert gpu.USE_GPU is True
    assert sys.modules["cupy"].used


def test_gpu_device_selection(monkeypatch) -> None:
    monkeypatch.setenv("FORZIUM_USE_GPU", "1")
    monkeypatch.setenv("FORZIUM_GPU_DEVICE", "2")

    class FakeCuda:
        class Device:
            def __init__(self, idx):
                FakeCupy.device = idx

            def use(self) -> None:  # pragma: no cover - no-op
                pass

    class FakeCupy:
        device = None

        def array(self, data):
            return data

        def asnumpy(self, arr):
            return arr

        cuda = FakeCuda()

    monkeypatch.setitem(sys.modules, "cupy", FakeCupy())
    reload_gpu()
    assert gpu.USE_GPU is True
    assert sys.modules["cupy"].device == 2


def test_elementwise_mul_cpu(monkeypatch) -> None:
    monkeypatch.delenv("FORZIUM_USE_GPU", raising=False)
    monkeypatch.delitem(sys.modules, "cupy", raising=False)
    reload_gpu()
    result = gpu.elementwise_mul([[1.0, 2.0]], [[3.0, 4.0]])
    assert result == [[3.0, 8.0]]


def test_elementwise_mul_gpu(monkeypatch) -> None:
    monkeypatch.setenv("FORZIUM_USE_GPU", "1")

    class FakeArray(list):
        def __mul__(self, other):
            return FakeArray(
                [[x * y for x, y in zip(r1, r2)] for r1, r2 in zip(self, other)]
            )

        def tolist(self):  # type: ignore[override]
            return list(self)

    class FakeCupy:
        used = False

        def array(self, data):
            FakeCupy.used = True
            return FakeArray(data)

        def asnumpy(self, arr):
            return arr

    monkeypatch.setitem(sys.modules, "cupy", FakeCupy())
    reload_gpu()
    result = gpu.elementwise_mul([[1.0, 2.0]], [[3.0, 4.0]])
    assert result == [[3.0, 8.0]]
    assert gpu.USE_GPU is True
    assert sys.modules["cupy"].used


def test_conv2d_cpu(monkeypatch) -> None:
    monkeypatch.delenv("FORZIUM_USE_GPU", raising=False)
    monkeypatch.delitem(sys.modules, "cupy", raising=False)
    reload_gpu()
    mat = [[1.0, 2.0], [3.0, 4.0]]
    ker = [[1.0]]
    assert gpu.conv2d(mat, ker) == mat


def test_benchmark(monkeypatch) -> None:
    monkeypatch.delenv("FORZIUM_USE_GPU", raising=False)
    monkeypatch.delitem(sys.modules, "cupy", raising=False)
    reload_gpu()
    data = [[1.0, 2.0], [3.0, 4.0]]
    metrics = gpu.benchmark_tensor_ops(data, data, [[1.0]], repeat=1)
    assert set(metrics) == {"elementwise_mul", "matmul", "conv2d"}
    assert set(metrics["elementwise_mul"]) == {"cpu_ms", "gpu_ms"}


def test_matmul_cpu(monkeypatch) -> None:
    monkeypatch.delenv("FORZIUM_USE_GPU", raising=False)
    monkeypatch.delitem(sys.modules, "cupy", raising=False)
    reload_gpu()
    result = gpu.matmul([[1.0, 2.0], [3.0, 4.0]], [[1.0], [1.0]])
    assert result == [[3.0], [7.0]]


def test_matmul_gpu(monkeypatch) -> None:
    monkeypatch.setenv("FORZIUM_USE_GPU", "1")

    class FakeArray(list):
        def __matmul__(self, other):
            return FakeArray(
                [
                    [sum(x * y for x, y in zip(r1, c2))]
                    for r1, c2 in zip(self, zip(*other))
                ]
            )

        def tolist(self):  # type: ignore[override]
            return list(self)

    class FakeCupy:
        used = False

        def array(self, data):
            FakeCupy.used = True
            return FakeArray(data)

        def asnumpy(self, arr):
            return arr

    monkeypatch.setitem(sys.modules, "cupy", FakeCupy())
    reload_gpu()
    result = gpu.matmul([[1.0, 2.0]], [[3.0], [4.0]])
    assert result == [[11.0]]
    assert gpu.USE_GPU is True
    assert sys.modules["cupy"].used
