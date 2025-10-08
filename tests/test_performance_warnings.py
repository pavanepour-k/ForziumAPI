"""Tests for performance warning system."""

import importlib
import os
import warnings
from unittest.mock import patch


class TestPerformanceWarnings:
    """Test performance warning system."""

    def test_forzium_engine_warning_on_import(self):
        """Test that warnings are emitted when Rust engine is not available."""
        with patch('forzium_engine._rust_engine', None):
            with patch('forzium_engine._RUST_AVAILABLE', False):
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    # Re-import the module to trigger the warning
                    import importlib
                    import forzium_engine
                    importlib.reload(forzium_engine)
                    
                    # Check that warning was emitted
                    assert len(w) >= 1
                    assert any("Rust engine not available" in str(warning.message) for warning in w)
                    assert any("Performance will be significantly degraded" in str(warning.message) for warning in w)

    def test_forzium_engine_fallback_warnings(self):
        """Test that fallback functions emit performance warnings."""
        with patch('forzium_engine._RUST_AVAILABLE', False):
            with patch('forzium_engine._rust_engine', None):
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    
                    import forzium_engine
                    importlib.reload(forzium_engine)
                    
                    # Test matrix multiplication warning
                    forzium_engine.matmul([[1.0, 2.0]], [[3.0], [4.0]])
                    
                    # Check that warning was emitted
                    assert len(w) >= 1
                    assert any("matrix multiplication" in str(warning.message) for warning in w)
                    assert any("10-100x slower" in str(warning.message) for warning in w)

    def test_gpu_service_warning_on_import(self):
        """Test that GPU service emits warnings when Rust functions are not available."""
        with patch('core.service.gpu._RUST_FUNCTIONS_AVAILABLE', False):
            with patch('core.service.gpu._rust_conv2d', None):
                with patch('core.service.gpu._rust_add', None):
                    with patch('core.service.gpu._rust_mul', None):
                        with patch('core.service.gpu._rust_matmul', None):
                            with warnings.catch_warnings(record=True) as w:
                                warnings.simplefilter("always")
                                # Re-import the module to trigger the warning
                                import importlib
                                import core.service.gpu
                                importlib.reload(core.service.gpu)
                                
                                # Check that warning was emitted
                                assert len(w) >= 1
                                assert any("Rust compute functions not available" in str(warning.message) for warning in w)

    def test_gpu_service_fallback_warnings(self):
        """Test that GPU service fallback functions emit performance warnings."""
        with patch('core.service.gpu._RUST_FUNCTIONS_AVAILABLE', False):
            with patch('core.service.gpu._rust_conv2d', None):
                with patch('core.service.gpu._rust_add', None):
                    with patch('core.service.gpu._rust_mul', None):
                        with patch('core.service.gpu._rust_matmul', None):
                            with patch('core.service.gpu.USE_GPU', False):
                                with warnings.catch_warnings(record=True) as w:
                                    warnings.simplefilter("always")
                                    
                                    import core.service.gpu
                                    importlib.reload(core.service.gpu)
                                    
                                    # Test elementwise addition warning
                                    core.service.gpu.elementwise_add([[1.0, 2.0]], [[3.0, 4.0]])
                                    
                                    # Check that warning was emitted
                                    assert len(w) >= 1
                                    assert any("elementwise addition" in str(warning.message) for warning in w)
                                    assert any("5-20x slower" in str(warning.message) for warning in w)

    def test_warning_suppression_environment_variable(self):
        """Test that warnings can be suppressed with environment variable."""
        with patch.dict(os.environ, {'FORZIUM_SUPPRESS_FALLBACK_WARNINGS': '1'}):
            with patch('forzium_engine._RUST_AVAILABLE', False):
                with patch('forzium_engine._rust_engine', None):
                    with warnings.catch_warnings(record=True) as w:
                        warnings.simplefilter("always")
                        
                        import forzium_engine
                        importlib.reload(forzium_engine)
                        
                        # Test matrix multiplication - should not emit warning
                        forzium_engine.matmul([[1.0, 2.0]], [[3.0], [4.0]])
                        
                        # Check that no performance warning was emitted
                        performance_warnings = [warning for warning in w 
                                             if "Performance impact" in str(warning.message)]
                        assert len(performance_warnings) == 0

    def test_gpu_warning_suppression_environment_variable(self):
        """Test that GPU service warnings can be suppressed with environment variable."""
        with patch.dict(os.environ, {'FORZIUM_SUPPRESS_FALLBACK_WARNINGS': '1'}):
            with patch('core.service.gpu._RUST_FUNCTIONS_AVAILABLE', False):
                with patch('core.service.gpu._rust_conv2d', None):
                    with patch('core.service.gpu._rust_add', None):
                        with patch('core.service.gpu._rust_mul', None):
                            with patch('core.service.gpu._rust_matmul', None):
                                with patch('core.service.gpu.USE_GPU', False):
                                    with warnings.catch_warnings(record=True) as w:
                                        warnings.simplefilter("always")
                                        
                                        import core.service.gpu
                                        importlib.reload(core.service.gpu)
                                        
                                        # Test elementwise addition - should not emit warning
                                        core.service.gpu.elementwise_add([[1.0, 2.0]], [[3.0, 4.0]])
                                        
                                        # Check that no performance warning was emitted
                                        performance_warnings = [warning for warning in w 
                                                             if "Performance impact" in str(warning.message)]
                                        assert len(performance_warnings) == 0

    def test_specific_operation_warnings(self):
        """Test that specific operations emit appropriate warnings."""
        with patch('forzium_engine._RUST_AVAILABLE', False):
            with patch('forzium_engine._rust_engine', None):
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    
                    import forzium_engine
                    importlib.reload(forzium_engine)
                    
                    # Test different operations and their specific warnings
                    test_cases = [
                        (forzium_engine.conv2d, "2D convolution", "50-500x slower"),
                        (forzium_engine.simd_matmul, "SIMD matrix multiplication", "20-200x slower"),
                        (forzium_engine.elementwise_add, "elementwise addition", "5-20x slower"),
                        (forzium_engine.normalize, "vector normalization", "3-10x slower"),
                    ]
                    
                    for func, operation, impact in test_cases:
                        w.clear()  # Clear previous warnings
                        
                        if func == forzium_engine.conv2d:
                            func([[1.0, 2.0], [3.0, 4.0]], [[1.0, 0.0], [0.0, 1.0]])
                        elif func == forzium_engine.simd_matmul:
                            func([[1.0, 2.0]], [[3.0], [4.0]])
                        elif func == forzium_engine.elementwise_add:
                            func([[1.0, 2.0]], [[3.0, 4.0]])
                        elif func == forzium_engine.normalize:
                            func([1.0, 2.0, 3.0])
                        
                        # Check that appropriate warning was emitted
                        assert len(w) >= 1
                        assert any(operation in str(warning.message) for warning in w)
                        assert any(impact in str(warning.message) for warning in w)

    def test_warning_message_content(self):
        """Test that warning messages contain all required information."""
        with patch('forzium_engine._RUST_AVAILABLE', False):
            with patch('forzium_engine._rust_engine', None):
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    
                    import forzium_engine
                    importlib.reload(forzium_engine)
                    
                    # Test matrix multiplication
                    forzium_engine.matmul([[1.0, 2.0]], [[3.0], [4.0]])
                    
                    # Find the performance warning
                    performance_warnings = [warning for warning in w 
                                         if "Performance impact" in str(warning.message)]
                    assert len(performance_warnings) >= 1
                    
                    warning_message = str(performance_warnings[0].message)
                    
                    # Check that message contains all required elements
                    assert "Using Python fallback for" in warning_message
                    assert "matrix multiplication" in warning_message
                    assert "Performance impact:" in warning_message
                    assert "10-100x slower" in warning_message
                    assert "Install Rust extension for optimal performance" in warning_message
