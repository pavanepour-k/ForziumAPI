#!/usr/bin/env python3
"""
Simple build script for ForziumAPI users.
This script builds the Rust extension and verifies the installation.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return True if successful."""
    print(f"> {description}...")
    try:
        # Use bytes mode and utf-8 encoding with errors='replace' to handle encoding issues
        result = subprocess.run(
            cmd, 
            check=True, 
            capture_output=True, 
            text=False,  # Use bytes mode
        )
        print(f"[SUCCESS] {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] {description} failed:")
        print(f"   Command: {' '.join(cmd)}")
        # Safely decode stderr with error handling
        error_msg = e.stderr.decode('utf-8', errors='replace') if e.stderr else 'No error output'
        print(f"   Error: {error_msg}")
        return False


def check_python_version() -> bool:
    """Check if Python version is 3.13."""
    if sys.version_info < (3, 13):
        print("[ERROR] Python 3.13 is required")
        return False
    print(f"[SUCCESS] Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True


def check_rust_installed() -> bool:
    """Check if Rust is installed."""
    try:
        result = subprocess.run(["rustc", "--version"], capture_output=True, text=False)
        if result.returncode == 0:
            # Safely decode stdout with error handling
            rust_version = result.stdout.decode('utf-8', errors='replace').strip()
            print(f"[SUCCESS] Rust detected: {rust_version}")
            return True
    except FileNotFoundError:
        pass
    
    print("[ERROR] Rust is not installed or not in PATH")
    print("   Please install Rust from https://rustup.rs/")
    return False


def install_dependencies() -> bool:
    """Install Python dependencies."""
    return run_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      "Installing Python dependencies")


def setup_build_environment():
    """Set up environment variables for the Rust build."""
    import os
    # Set environment variables for PyO3 and maturin
    env_vars = {
        "PYO3_PYTHON": sys.executable,  # Use the current Python interpreter
        "PYTHONIOENCODING": "utf-8",   # Force UTF-8 encoding for Python I/O
    }
    
    # Update environment
    os.environ.update(env_vars)
    print("> Setting build environment variables:")
    for key, value in env_vars.items():
        print(f"   {key}={value}")

def build_rust_extension() -> bool:
    """Build the Rust extension using maturin."""
    # Set up the build environment
    setup_build_environment()
    
    # Install maturin if not already installed
    print("> Installing maturin...")
    if not run_command([sys.executable, "-m", "pip", "install", "maturin"], 
                       "Installing maturin"):
        return False
    
    # Build the extension using the Python module directly
    return run_command([sys.executable, "-m", "maturin", "develop", "--release"], 
                      "Building Rust extension")


def verify_installation() -> bool:
    """Verify that the installation works."""
    try:
        import forzium
        import forzium_engine
        print("[SUCCESS] ForziumAPI modules imported successfully")
        print(f"   Version: {forzium.__version__}")
        return True
    except ImportError as e:
        print(f"[ERROR] Failed to import ForziumAPI modules: {e}")
        return False


def main():
    """Main build process."""
    print("[START] ForziumAPI Build Script")
    print("=" * 40)
    
    # Check prerequisites
    if not check_python_version():
        sys.exit(1)
    
    if not check_rust_installed():
        sys.exit(1)
    
    # Build process
    if not install_dependencies():
        sys.exit(1)
    
    if not build_rust_extension():
        sys.exit(1)
    
    if not verify_installation():
        sys.exit(1)
    
    print("\n[COMPLETE] Build completed successfully!")
    print("   You can now run: python run_server.py")


if __name__ == "__main__":
    main()

