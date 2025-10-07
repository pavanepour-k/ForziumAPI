#!/usr/bin/env python3
"""
Debug script for ForziumAPI users.
This script helps diagnose common issues and verify the installation.
"""

import sys
import importlib
from pathlib import Path


def check_python_version():
    """Check Python version."""
    print(f"Python version: {sys.version}")
    if sys.version_info < (3, 12):
        print("⚠️  Warning: Python 3.12+ is recommended")
    else:
        print("✅ Python version is compatible")


def check_imports():
    """Check if all required modules can be imported."""
    modules = [
        ("forzium", "ForziumAPI framework"),
        ("forzium_engine", "Rust engine"),
        ("core", "Core application logic"),
    ]
    
    print("\n📦 Checking module imports:")
    for module_name, description in modules:
        try:
            module = importlib.import_module(module_name)
            version = getattr(module, "__version__", "unknown")
            print(f"✅ {module_name}: {description} (v{version})")
        except ImportError as e:
            print(f"❌ {module_name}: Failed to import - {e}")


def check_rust_extension():
    """Check if Rust extension is working."""
    print("\n🦀 Checking Rust extension:")
    try:
        import forzium_engine
        print("✅ Rust extension imported successfully")
        
        # Try to call a simple function
        if hasattr(forzium_engine, 'noop'):
            forzium_engine.noop()
            print("✅ Rust functions are callable")
        else:
            print("⚠️  Rust extension loaded but no test functions found")
            
    except ImportError as e:
        print(f"❌ Rust extension failed to import: {e}")
        print("   Try running: python build.py")


def check_server_creation():
    """Check if server can be created."""
    print("\n🌐 Checking server creation:")
    try:
        from core import server
        print("✅ Server module imported successfully")
        
        # Check if server has required methods
        if hasattr(server, 'serve') and hasattr(server, 'shutdown'):
            print("✅ Server has required methods")
        else:
            print("⚠️  Server missing some required methods")
            
    except ImportError as e:
        print(f"❌ Server module failed to import: {e}")


def check_app_creation():
    """Check if ForziumApp can be created."""
    print("\n📱 Checking app creation:")
    try:
        from forzium import ForziumApp
        app = ForziumApp()
        print("✅ ForziumApp created successfully")
        
        # Check if app has basic methods
        if hasattr(app, 'get') and hasattr(app, 'post'):
            print("✅ App has routing methods")
        else:
            print("⚠️  App missing routing methods")
            
    except Exception as e:
        print(f"❌ ForziumApp creation failed: {e}")


def check_file_structure():
    """Check if required files exist."""
    print("\n📁 Checking file structure:")
    required_files = [
        "main.py",
        "run_server.py", 
        "requirements.txt",
        "pyproject.toml",
        "rust-toolchain.toml",
    ]
    
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - Missing")


def main():
    """Main debug process."""
    print("🔍 ForziumAPI Debug Script")
    print("=" * 40)
    
    check_python_version()
    check_file_structure()
    check_imports()
    check_rust_extension()
    check_server_creation()
    check_app_creation()
    
    print("\n" + "=" * 40)
    print("🏁 Debug check completed!")
    print("\nIf you see any ❌ errors above, try:")
    print("1. Run: python build.py")
    print("2. Check: pip install -r requirements.txt")
    print("3. Verify: Rust is installed (rustc --version)")


if __name__ == "__main__":
    main()

