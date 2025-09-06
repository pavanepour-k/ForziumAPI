"""Minimal validation utilities replacing Pydantic."""

from __future__ import annotations

from dataclasses import MISSING, dataclass, fields
from typing import Any, Callable, ClassVar, Dict, List, get_args, get_origin

Validator = Callable[[type, Dict[str, Any]], Dict[str, Any]]
FieldValidator = Callable[[type, Any], Any]


def model_validator(
    *,
    mode: str = "before",
) -> Callable[[Validator], classmethod]:
    """Decorator to register class-level validators."""

    def decorator(func: Validator) -> classmethod:
        func.__forzium_model_validator__ = mode  # type: ignore[attr-defined]
        return classmethod(func)

    return decorator


def field_validator(
    field: str, *, mode: str = "before"
) -> Callable[[FieldValidator], classmethod]:
    """Decorator to register field-level validators."""

    def decorator(func: FieldValidator) -> classmethod:
        func.__forzium_field_validator__ = (field, mode)  # type: ignore[attr-defined]
        return classmethod(func)

    return decorator


class BaseModel:
    """Lightweight stand-in for Pydantic's BaseModel."""

    _model_validators: ClassVar[List[tuple[str, Validator]]]
    _field_validators: ClassVar[Dict[str, List[tuple[str, FieldValidator]]]]

    def __init_subclass__(cls) -> None:  # pragma: no cover - trivial
        dataclass(eq=False)(cls)
        cls._model_validators = []
        cls._field_validators = {}
        for name in dir(cls):
            attr = getattr(cls, name)
            func = getattr(attr, "__func__", attr)
            mode = getattr(func, "__forzium_model_validator__", None)
            if mode is not None:
                cls._model_validators.append((mode, func))
            fv = getattr(func, "__forzium_field_validator__", None)
            if fv is not None:
                field, fmode = fv
                cls._field_validators.setdefault(field, []).append((fmode, func))
        setattr(cls, "__init__", BaseModel.__init__)  # ensure custom init

    def __init__(self, **data: Any) -> None:
        raw = dict(data)
        values: Dict[str, Any] = {}
        for f in fields(self):  # type: ignore[arg-type]
            if f.name in raw:
                values[f.name] = raw[f.name]
            elif f.default is not MISSING:
                values[f.name] = f.default
            elif f.default_factory is not MISSING:  # type: ignore[call-arg]
                values[f.name] = f.default_factory()
            else:
                raise ValueError("Field required")
        for mode, validator in self._model_validators:
            if mode == "before":
                values = validator(self.__class__, values)
        for f in fields(self):  # type: ignore[arg-type]
            val = values[f.name]
            for mode, func in self._field_validators.get(f.name, []):
                if mode == "before":
                    val = func(self.__class__, val)
            setattr(self, f.name, val)
            for mode, func in self._field_validators.get(f.name, []):
                if mode == "after":
                    new_val = func(self.__class__, getattr(self, f.name))
                    setattr(self, f.name, new_val)
        for mode, validator in self._model_validators:
            if mode == "after":
                validator(self.__class__, self.dict())

    def dict(self) -> Dict[str, Any]:  # pragma: no cover - simple
        return {
            field.name: getattr(self, field.name) for field in fields(self)
        }  # type: ignore[arg-type]

    def model_dump(self) -> Dict[str, Any]:  # pragma: no cover - alias
        return self.dict()

    @classmethod
    def model_json_schema(cls) -> Dict[str, Any]:
        """Return a JSON schema for the model fields."""

        def type_schema(tp: Any) -> Dict[str, Any]:
            origin = get_origin(tp)
            if origin in (list, List):
                (item_type,) = get_args(tp) or (Any,)
                return {"type": "array", "items": type_schema(item_type)}
            if tp is int:
                return {"type": "integer"}
            if tp is float:
                return {"type": "number"}
            if tp is bool:
                return {"type": "boolean"}
            if tp is str:
                return {"type": "string"}
            return {"type": "object"}

        props: Dict[str, Any] = {}
        required: List[str] = []
        for f in fields(cls):  # type: ignore[arg-type]
            sch = type_schema(f.type)
            if f.default is not MISSING:
                sch["default"] = f.default
            elif f.default_factory is not MISSING:  # type: ignore[call-arg]
                sch["default"] = f.default_factory()
            else:
                required.append(f.name)
            props[f.name] = sch
        schema: Dict[str, Any] = {
            "title": cls.__name__,
            "type": "object",
            "properties": props,
        }
        if required:
            schema["required"] = required
        return schema


__all__ = ["BaseModel", "model_validator", "field_validator"]
