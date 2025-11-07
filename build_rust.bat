@echo off
set VIRTUAL_ENV=c:/Users/Admin/Documents/work/ForziumAPI/python3.13
set PYO3_PYTHON=c:/Users/Admin/Documents/work/ForziumAPI/python3.13/python.exe
cd core/rust_engine
c:/Users/Admin/Documents/work/ForziumAPI/python3.13/Scripts/maturin develop --release
