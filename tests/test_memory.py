from core.python_api.services import orchestration_service as svc


def test_force_gc_exists():
    assert hasattr(svc.forzium_engine, "force_gc")
    svc.forzium_engine.force_gc()
