# flake8: noqa
"""Decorator-based routing tied directly to the Rust server."""

import asyncio
import inspect
import json
import logging
import os
import re
import sys
import threading
import time
from dataclasses import MISSING, fields, is_dataclass
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Dict,
    List,
    Tuple,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)
from urllib.parse import parse_qs

from infrastructure.monitoring import (
    current_trace_span,
    get_metric,
    log_push_hints,
    mark_observability_ready,
    observability_health,
    observability_ready,
    notify_telemetry_finalizers,
    prometheus_metrics,
    record_latency,
    record_metric,
    start_span,
)

from .dependency import BackgroundTasks, Depends, Request
from .dependency import Response as HTTPResponse
from .dependency import solve_dependencies
from .http2 import _begin as _push_begin
from .http2 import _end as _push_end
from .http2 import format_link_header
from .middleware import RateLimitMiddleware
from .responses import HTTPException, StreamingResponse
from .websockets import WebSocket

_LOGGER = logging.getLogger("forzium")

try:
    from pydantic import BaseModel as PydanticBaseModel
    from pydantic import ValidationError as PydanticValidationError
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    _LOGGER.warning(
        "Pydantic is unavailable; request validation will be limited.",
        exc_info=True,
    )
    PydanticBaseModel = None  # type: ignore[assignment]
    PydanticValidationError = None  # type: ignore[assignment]
except ImportError:  # pragma: no cover - optional dependency misconfiguration
    _LOGGER.error(
        "Pydantic import failed due to an ImportError; request validation will be disabled.",
        exc_info=True,
    )
    PydanticBaseModel = None  # type: ignore[assignment]
    PydanticValidationError = None  # type: ignore[assignment]
    
TypeAdapter = None  # type: ignore[assignment]
if PydanticBaseModel is not None:  # pragma: no branch - cache probe
    import pydantic  # type: ignore  # noqa: WPS433 (runtime optional dependency)

    TypeAdapter = getattr(pydantic, "TypeAdapter", None)

_TYPE_ADAPTER_CACHE: dict[Any, Any] = {}
_ADAPTER_UNAVAILABLE = object()


def _get_type_adapter(tp: Any) -> Any | None:
    """Return a cached ``TypeAdapter`` for *tp* when available."""

    if TypeAdapter is None:
        return None
    if tp in _TYPE_ADAPTER_CACHE:
        return _TYPE_ADAPTER_CACHE[tp]
    try:
        adapter = TypeAdapter(tp)  # type: ignore[misc]
    except Exception:  # pragma: no cover - passthrough to manual coercion
        _TYPE_ADAPTER_CACHE[tp] = None
        return None
    _TYPE_ADAPTER_CACHE[tp] = adapter
    return adapter


def _validate_with_type_adapter(value: Any, tp: Any, loc: list[Any]) -> Any:
    """Validate *value* against *tp* using Pydantic when possible."""

    adapter = _get_type_adapter(tp)
    if adapter is None:
        return _ADAPTER_UNAVAILABLE
    try:
        return adapter.validate_python(value)
    except PydanticValidationError as exc:  # pragma: no cover - parity guard
        base_loc = list(loc)
        errors: list[dict[str, Any]] = []
        for err in exc.errors():
            err.pop("url", None)
            err_loc = [part for part in err.get("loc", ()) if part != "__root__"]
            input_value = err.get("input")
            if input_value == {}:
                input_value = None
            errors.append(
                {
                    "loc": base_loc + err_loc,
                    "msg": err.get("msg", ""),
                    "type": err.get("type", "value_error"),
                    "input": input_value,
                }
            )
        raise RequestValidationError(base_loc, "validation error", errors=errors) from exc
    except TypeError:  # pragma: no cover - defer to manual coercion
        return _ADAPTER_UNAVAILABLE


class RequestValidationError(Exception):
    """Internal validation error capturing location and message."""

    def __init__(
        self,
        loc: list[Any],
        msg: str,
        typ: str = "value_error",
        *,
        input_value: Any | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(msg)
        if errors is not None:
            self._errors = errors
        else:
            self._errors = [
                {
                    "loc": list(loc),
                    "msg": msg,
                    "type": typ,
                    "input": input_value,
                }
            ]

    def errors(self) -> list[dict[str, Any]]:
        return self._errors


class DependencyValidationError(Exception):
    """Dependency validation error mirroring FastAPI's 422 payload."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__("dependency validation error")
        self._errors = errors

    def errors(self) -> list[dict[str, Any]]:
        return self._errors


try:
    from graphql import (
        ExecutionResult,
        GraphQLObjectType,
        GraphQLSchema,
        graphql_sync,
        parse,
        subscribe,
    )

    _GRAPHQL_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    ExecutionResult = GraphQLObjectType = GraphQLSchema = None  # type: ignore[assignment]
    graphql_sync = parse = subscribe = None  # type: ignore[assignment]
    _GRAPHQL_AVAILABLE = False


def _coerce_value(value: Any, tp: Any, loc: list[Any] | None = None) -> Any:
    """Coerce ``value`` to type ``tp`` recursively."""
    if loc is None:
        loc = []
    else:
        loc = list(loc)
    adapter_result = _validate_with_type_adapter(value, tp, loc)
    if adapter_result is not _ADAPTER_UNAVAILABLE:
        return adapter_result
    origin = get_origin(tp)
    if is_dataclass(tp):
        if not isinstance(value, dict):
            raise RequestValidationError(
                loc,
                "invalid body",
                "type_error",
                input_value=value,
            )
        data: dict[str, Any] = {}
        for f in fields(tp):  # type: ignore[arg-type]
            if f.name in value:
                try:
                    data[f.name] = _coerce_value(
                        value[f.name], f.type, loc + [f.name]
                    )
                except RequestValidationError as exc:
                    raise exc
            elif f.default is not MISSING and f.default_factory is MISSING:
                pass
            elif f.default_factory is not MISSING:  # type: ignore[misc]
                pass
            else:
                raise RequestValidationError(
                    loc + [f.name],
                    "Field required",
                    "missing",
                    input_value=value,
                )
        return tp(**data)
    if (
        PydanticBaseModel is not None
        and inspect.isclass(tp)
        and issubclass(tp, PydanticBaseModel)
    ):
        if not isinstance(value, dict):
            raise RequestValidationError(
                loc,
                "invalid body",
                "type_error",
                input_value=value,
            )
        if hasattr(tp, "model_validate"):
            return tp.model_validate(value)  # type: ignore[attr-defined]
        return tp.parse_obj(value)  # type: ignore[attr-defined]
    if origin in (list, List):
        (item_type,) = get_args(tp) or (Any,)
        result = []
        for idx, v in enumerate(value):
            result.append(
                _coerce_value(v, item_type, loc + [idx])
            )
        return result
    if tp is int:
        try:
            return int(value)
        except (TypeError, ValueError):  # noqa: BLE001
            raise RequestValidationError(
                loc,
                "value is not a valid integer",
                "int_parsing",
                input_value=value,
            )
    if tp is float:
        try:
            return float(value)
        except (TypeError, ValueError):  # noqa: BLE001
            raise RequestValidationError(
                loc,
                "value is not a valid float",
                "float_parsing",
                input_value=value,
            )
    if tp is bool:
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "on", "yes"}:
            return True
        if normalized in {"0", "false", "off", "no"}:
            return False
        raise RequestValidationError(
            loc,
            "value could not be parsed to a boolean",
            "bool_parsing",
            input_value=value,
        )
    if tp is str:
        return str(value)
    return value


def _iter_model_fields(tp: Any) -> list[tuple[str, Any]]:
    """Return iterable of (name, field_info) pairs for a Pydantic model."""

    fields_v2 = getattr(tp, "model_fields", None)
    if isinstance(fields_v2, dict):
        return list(fields_v2.items())
    fields_v1 = getattr(tp, "__fields__", None)
    if isinstance(fields_v1, dict):
        return list(fields_v1.items())
    return []


def _make_dependency_parser(name: str, annotation: Any) -> Callable[[Request], Any]:
    """Return a dependency callable inferred from a parameter annotation."""

    if annotation is inspect._empty:
        raise TypeError(
            f"Depends() for parameter '{name}' requires a type annotation"
        )
    if annotation is Request or annotation == Request:
        return lambda request: request
    if (
        PydanticBaseModel is not None
        and inspect.isclass(annotation)
        and issubclass(annotation, PydanticBaseModel)
    ):

        def _dependency(request: Request) -> Any:
            payload: dict[str, Any] = {}
            for field_name, info in _iter_model_fields(annotation):
                alias = getattr(info, "alias", None)
                key = alias or field_name
                if key in request.query_params:
                    payload[field_name] = request.query_params[key]
            try:
                if hasattr(annotation, "model_validate"):
                    return annotation.model_validate(payload)  # type: ignore[attr-defined]
                return annotation.parse_obj(payload)  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: BLE001
                if (
                    PydanticValidationError is not None
                    and isinstance(exc, PydanticValidationError)
                ):
                    errors: list[dict[str, Any]] = []
                    for err in exc.errors():
                        err.pop("url", None)
                        input_value = err.get("input")
                        if input_value == {}:
                            input_value = None
                        errors.append(
                            {
                                "loc": [
                                    "query",
                                    *err.get("loc", []),
                                ],
                                "msg": err.get("msg", ""),
                                "type": err.get("type", "value_error"),
                                "input": input_value,
                            }
                        )
                    raise DependencyValidationError(errors) from exc
                raise

        return _dependency

    if is_dataclass(annotation):

        def _dependency(request: Request) -> Any:
            errors: list[dict[str, Any]] = []
            data: dict[str, Any] = {}
            for field in fields(annotation):  # type: ignore[arg-type]
                if field.name in request.query_params:
                    raw = request.query_params[field.name]
                    try:
                        data[field.name] = _coerce_value(
                            raw, field.type, ["query", field.name]
                        )
                    except RequestValidationError as exc:
                        errors.extend(exc.errors())
                    except ValueError as exc:  # noqa: BLE001
                        errors.append(
                            {
                                "loc": ["query", field.name],
                                "msg": str(exc),
                                "type": "value_error",
                                "input": raw,
                            }
                        )
                elif field.default is not MISSING:
                    data[field.name] = field.default
                elif field.default_factory is not MISSING:  # type: ignore[misc]
                    data[field.name] = field.default_factory()
                else:
                    errors.append(
                        {
                            "loc": ["query", field.name],
                            "msg": "Field required",
                            "type": "missing",
                            "input": None,
                        }
                    )
            if errors:
                raise DependencyValidationError(errors)
            return annotation(**data)

        return _dependency

    def _dependency(request: Request) -> Any:
        raw = request.query_params.get(name)
        if raw is None:
            raise DependencyValidationError(
                [
                    {
                        "loc": ["query", name],
                        "msg": "Field required",
                        "type": "missing",
                        "input": None,
                    }
                ]
            )
        try:
            return _coerce_value(raw, annotation, ["query", name])
        except RequestValidationError as exc:
            raise DependencyValidationError(exc.errors()) from exc
        except ValueError as exc:  # noqa: BLE001
            raise DependencyValidationError(
                [
                    {
                        "loc": ["query", name],
                        "msg": str(exc),
                        "type": "value_error",
                        "input": raw,
                    }
                ]
            ) from exc

    return _dependency


class ForziumApp:
    """Register Python handlers with the Rust HTTP server."""

    def __init__(
        self,
        server: Any | None = None,
        *,
        max_upload_size: int | None = None,
        allowed_mime_types: set[str] | None = None,
        task_queue: Any | None = None,
    ) -> None:
        self.server = server
        self.max_upload_size = max_upload_size
        self.allowed_mime_types = allowed_mime_types
        self.task_queue = task_queue
        self.routes: list[dict[str, Any]] = []
        self.ws_routes: list[dict[str, Any]] = []
        self._request_hooks: list[
            Callable[
                [bytes, tuple, bytes],
                tuple[
                    bytes, tuple, bytes, tuple[int, str, dict[str, str]] | None
                ],  # noqa: E501
            ]
        ] = []
        self._response_hooks: list[
            Callable[
                [int, str, dict[str, str]], tuple[int, str, dict[str, str]]
            ]  # noqa: E501
        ] = []
        self._asgi_middleware: list[
            Callable[
                [Request, Callable[[Request], HTTPResponse]], HTTPResponse
            ]  # noqa: E501
        ] = []
        self._startup_hooks: list[Callable[[], Any]] = []
        self._shutdown_hooks: list[Callable[[], Any]] = []
        self._schema_route_registered = False
        self._metrics_route_registered = False
        self._docs_route_registered = False
        self._observability_route_registered = False
        self.security_schemes: dict[str, Any] = {}
        self.dependency_overrides: dict[Callable[..., Any], Callable[..., Any]] = {}
        self._openapi_customizer: Callable[
            [dict[str, Any]], dict[str, Any]
        ] | None = None
        self.exception_handlers: dict[
            type[Exception], Callable[[Request, Exception], Any]
        ] = {}
        self._configure_rate_limit_from_env()
        self._register_observability_routes()

    def _configure_rate_limit_from_env(self) -> None:
        value = os.getenv("FORZIUM_RATE_LIMIT")
        if not value:
            return
        try:
            limit = int(value)
        except ValueError as exc:
            raise ValueError(
                "FORZIUM_RATE_LIMIT must be a positive integer"
            ) from exc
        if limit <= 0:
            raise ValueError("FORZIUM_RATE_LIMIT must be a positive integer")
        window_value = os.getenv("FORZIUM_RATE_LIMIT_WINDOW")
        if window_value:
            try:
                window = float(window_value)
            except ValueError as exc:
                raise ValueError(
                    "FORZIUM_RATE_LIMIT_WINDOW must be a positive number"
                ) from exc
        else:
            window = 1.0
        if window <= 0:
            raise ValueError("FORZIUM_RATE_LIMIT_WINDOW must be positive")
        scope = os.getenv("FORZIUM_RATE_LIMIT_SCOPE", "client").strip().lower()
        header_override = os.getenv("FORZIUM_RATE_LIMIT_IDENTIFIER_HEADER", "").strip()

        def _header_identifier(header_name: str) -> Callable[[Request], str]:
            key = header_name.lower()

            def _identifier(request: Request) -> str:
                headers = getattr(request, "headers", {}) or {}
                raw_value = str(headers.get(key, ""))
                if not raw_value:
                    return "anonymous"
                first = raw_value.split(",", 1)[0].strip()
                return first or "anonymous"

            return _identifier

        identifier: Callable[[Request], str] | None = None
        if scope in {"client", "ip"}:
            per_client = True
            include_path = False
            if header_override:
                identifier = _header_identifier(header_override)
        elif scope == "global":
            per_client = False
            include_path = False
        elif scope == "path":
            per_client = False
            include_path = True
        elif scope in {"client_path", "client+path", "ip_path", "ip+path"}:
            per_client = True
            include_path = True
            if header_override:
                identifier = _header_identifier(header_override)
        elif scope in {"user", "user_path", "user+path"}:
            per_client = True
            include_path = scope != "user"
            header_name = header_override or "x-user-id"
            if not header_name.strip():
                raise ValueError(
                    "FORZIUM_RATE_LIMIT_IDENTIFIER_HEADER must not be empty"
                )
            identifier = _header_identifier(header_name)
        else:
            raise ValueError(
                "FORZIUM_RATE_LIMIT_SCOPE must be one of: client, ip, global, path, client_path, user, user_path"
            )
        middleware = RateLimitMiddleware(
            limit=limit,
            window=window,
            per_client=per_client,
            include_path=include_path,
            identifier=identifier,
        )
        self._asgi_middleware.append(middleware)

    def add_security_scheme(self, name: str, scheme: dict[str, Any]) -> None:
        """Register security *scheme* under *name*."""

        self.security_schemes[name] = scheme

    def customize_openapi(
        self, func: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> None:
        """Apply *func* to modify generated OpenAPI documents."""

        self._openapi_customizer = func

    def add_exception_handler(
        self, exc_type: type[Exception], handler: Callable[[Request, Exception], Any]
    ) -> None:
        """Register a custom *handler* for exceptions of type *exc_type*."""

        self.exception_handlers[exc_type] = handler

    def _lookup_handler(
        self, exc: Exception
    ) -> Callable[[Request, Exception], Any] | None:
        for cls in type(exc).__mro__:
            if cls in self.exception_handlers:
                return self.exception_handlers[cls]
        return None

    @staticmethod
    def _choose_media(accept: str | None) -> str | None:
        supported = ("application/json", "text/plain")
        if not accept:
            return None
        best = None
        best_q = -1.0
        for part in accept.split(","):
            media, *params = part.split(";")
            q = 1.0
            for param in params:
                param = param.strip()
                if param.startswith("q="):
                    try:
                        q = float(param[2:])
                    except ValueError:
                        q = 1.0
            media = media.strip()
            if media in supported and q > best_q:
                best = media
                best_q = q
        return best

    def openapi_schema(self) -> dict[str, Any]:
        """Generate an OpenAPI document for the registered routes."""

        paths: dict[str, dict[str, dict[str, Any]]] = {}
        components: dict[str, dict[str, Any]] = {
            "schemas": {
                "ValidationError": {
                    "type": "object",
                    "properties": {
                        "loc": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "msg": {"type": "string"},
                        "type": {"type": "string"},
                    },
                    "required": ["loc", "msg", "type"],
                },
                "HTTPValidationError": {
                    "type": "object",
                    "properties": {
                        "detail": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/ValidationError"},
                        }
                    },
                },
            },
            "securitySchemes": self.security_schemes,
        }
        tag_set: set[str] = set()

        def type_schema(tp: Any) -> dict[str, Any]:
            origin = get_origin(tp)
            if is_dataclass(tp):
                name = getattr(tp, "__name__", tp.__class__.__name__)
                if name not in components["schemas"]:
                    props: dict[str, Any] = {}
                    required: list[str] = []
                    for f in fields(tp):  # type: ignore[arg-type]
                        props[f.name] = type_schema(f.type)
                        if f.default is MISSING and f.default_factory is MISSING:
                            required.append(f.name)
                    schema: dict[str, Any] = {
                        "type": "object",
                        "properties": props,
                    }
                    if required:
                        schema["required"] = required
                    components["schemas"][name] = schema
                return {"$ref": f"#/components/schemas/{name}"}
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

        for route in self.routes:
            responses: dict[str, dict[str, Any]] = {"200": {"description": "OK"}}
            ret = inspect.signature(route["func"]).return_annotation
            responses["200"]["content"] = {
                "application/json": {"schema": type_schema(ret)}
            }
            for code, resp in route.get("responses", {}).items():
                responses[str(code)] = resp
            if route.get("body_param") or route.get("query_params"):
                responses.setdefault(
                    "422",
                    {
                        "description": "Validation Error",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/HTTPValidationError"
                                }
                            }
                        },
                    },
                )
            op: dict[str, Any] = {"responses": responses}
            if route.get("summary"):
                op["summary"] = route["summary"]
            if route.get("description"):
                op["description"] = route["description"]
            params = []
            for name, anno in route.get("path_params", []):
                params.append(
                    {
                        "name": name,
                        "in": "path",
                        "required": True,
                        "schema": type_schema(anno),
                    }
                )
            for name, anno in route.get("query_params", []):
                params.append(
                    {
                        "name": name,
                        "in": "query",
                        "required": False,
                        "schema": type_schema(anno),
                    }
                )
            if params:
                op["parameters"] = params
            if route.get("body_param"):
                _, anno = route["body_param"]
                op["requestBody"] = {
                    "content": {"application/json": {"schema": type_schema(anno)}},
                    "required": True,
                }
            if route.get("tags"):
                op["tags"] = route["tags"]
                tag_set.update(route["tags"])
            paths.setdefault(route["path"], {})[route["method"].lower()] = op
        for ws in self.ws_routes:
            paths.setdefault(ws["path"], {}).setdefault(
                "get", {"responses": {"200": {"description": "OK"}}}
            )

        doc: dict[str, Any] = {
            "openapi": "3.0.0",
            "paths": paths,
            "components": components,
        }
        if tag_set:
            doc["tags"] = [{"name": t} for t in sorted(tag_set)]
        if self._openapi_customizer:
            doc = self._openapi_customizer(doc)
        return doc

    def _register_schema_route(self) -> None:
        if self._schema_route_registered:
            return
        self._schema_route_registered = True

        def _schema() -> dict[str, Any]:
            return self.openapi_schema()

        self.routes.append(
            {
                "method": "GET",
                "path": "/openapi.json",
                "host": None,
                "func": _schema,
                "param_names": [],
                "param_converters": {},
                "query_params": [],
                "body_param": None,
                "expects_body": False,
                "dependencies": [],
                "expects_request": False,
            }
        )
        if self.server is not None:
            handler = self._make_handler(
                _schema, [], {}, [], None, [], False, "GET", "/openapi.json"
            )
            add_route = getattr(self.server, "add_route")
            sig = inspect.signature(add_route)
            if "host" in sig.parameters:
                add_route(
                    "GET",
                    "/openapi.json",
                    lambda b, p, q, hdrs=None, h=handler: h(b, p, q, hdrs),
                    host=None,
                )
            else:
                add_route(
                    "GET",
                    "/openapi.json",
                    lambda b, p, q, hdrs=None, h=handler: h(b, p, q, hdrs),
                )

    def _register_metrics_route(self) -> None:
        if self._metrics_route_registered:
            return
        self._metrics_route_registered = True

        def _metrics() -> HTTPResponse:
            return HTTPResponse(
                prometheus_metrics(),
                media_type="text/plain; version=0.0.4; charset=utf-8",
            )

        self.routes.append(
            {
                "method": "GET",
                "path": "/metrics",
                "host": None,
                "func": _metrics,
                "param_names": [],
                "param_converters": {},
                "query_params": [],
                "body_param": None,
                "expects_body": False,
                "dependencies": [],
                "expects_request": False,
            }
        )
        if self.server is not None:
            handler = self._make_handler(
                _metrics, [], {}, [], None, [], False, "GET", "/metrics"
            )
            add_route = getattr(self.server, "add_route")
            sig = inspect.signature(add_route)
            if "host" in sig.parameters:
                add_route(
                    "GET",
                    "/metrics",
                    lambda b, p, q, hdrs=None, h=handler: h(b, p, q, hdrs),
                    host=None,
                )
            else:
                add_route(
                    "GET",
                    "/metrics",
                    lambda b, p, q, hdrs=None, h=handler: h(b, p, q, hdrs),
                )

    def _register_docs_routes(self) -> None:
        if self._docs_route_registered:
            return
        self._docs_route_registered = True

        swagger_html = """<!DOCTYPE html>
<html>
<head>
<link rel=\"stylesheet\"
 href=\"https://unpkg.com/swagger-ui-dist/swagger-ui.css\">
</head>
<body>
<div id=\"swagger-ui\"></div>
<script src=\"https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js\"></script>
<script>
SwaggerUIBundle({url: \"/openapi.json\", dom_id: \"#swagger-ui\"});
</script>
</body>
</html>"""

        redoc_html = """<!DOCTYPE html>
<html>
<head>
<script src=\"https://unpkg.com/redoc@next/bundles/redoc.standalone.js\"></script>
</head>
<body>
<redoc spec-url=\"/openapi.json\"></redoc>
</body>
</html>"""

        def _swagger() -> str:
            return swagger_html

        def _redoc() -> str:
            return redoc_html

        for path, func in [("/docs", _swagger), ("/redoc", _redoc)]:
            self.routes.append(
                {
                    "method": "GET",
                    "path": path,
                    "host": None,
                    "func": func,
                    "param_names": [],
                    "param_converters": {},
                    "query_params": [],
                    "body_param": None,
                    "expects_body": False,
                    "dependencies": [],
                    "expects_request": False,
                }
            )
            if self.server is not None:
                handler = self._make_handler(
                    func, [], {}, [], None, [], False, "GET", path
                )
                add_route = getattr(self.server, "add_route")
                sig = inspect.signature(add_route)
                if "host" in sig.parameters:
                    add_route(
                        "GET",
                        path,
                        lambda b, p, q, hdrs=None, h=handler: h(b, p, q, hdrs),
                        host=None,
                    )
                else:
                    add_route(
                        "GET",
                        path,
                        lambda b, p, q, hdrs=None, h=handler: h(b, p, q, hdrs),
                    )

    def _register_observability_routes(self) -> None:
        if self._observability_route_registered:
            return
        self._observability_route_registered = True

        def _obs_ready() -> tuple[int, dict[str, Any]]:
            payload = observability_health()
            if not payload.get("ready", False):
                payload = mark_observability_ready(
                    source="healthcheck",
                    metadata={"endpoint": "/observability/ready"},
                )
            status = 200 if payload.get("ready", False) else 503
            return status, payload

        self.routes.append(
            {
                "method": "GET",
                "path": "/observability/ready",
                "host": None,
                "func": _obs_ready,
                "param_names": [],
                "param_converters": {},
                "query_params": [],
                "body_param": None,
                "expects_body": False,
                "dependencies": [],
                "expects_request": False,
            }
        )
        if self.server is not None:
            handler = self._make_handler(
                _obs_ready,
                [],
                {},
                [],
                None,
                [],
                False,
                "GET",
                "/observability/ready",
            )
            add_route = getattr(self.server, "add_route")
            sig = inspect.signature(add_route)
            if "host" in sig.parameters:
                add_route(
                    "GET",
                    "/observability/ready",
                    lambda b, p, q, hdrs=None, h=handler: h(b, p, q, hdrs),
                    host=None,
                )
            else:
                add_route(
                    "GET",
                    "/observability/ready",
                    lambda b, p, q, hdrs=None, h=handler: h(b, p, q, hdrs),
                )

    def _extract_params(
        self, path: str
    ) -> tuple[list[str], Dict[str, Callable[[str], Any]]]:
        specs = re.findall(r"{([^}:]+)(?::([^}]+))?}", path)
        names: list[str] = []
        convs: Dict[str, Callable[[str], Any]] = {}
        for name, typ in specs:
            names.append(name)
            if typ == "int":
                convs[name] = int
            elif typ == "float":
                convs[name] = float
            elif typ == "bool":
                convs[name] = lambda v: v.lower() in ("1", "true", "on", "yes")
        return names, convs

    def route(
        self,
        path: str,
        method: str,
        host: str | None = None,
        tags: list[str] | None = None,
        responses: dict[int | str, dict[str, Any]] | None = None,
        dependencies: list[Depends] | None = None,
        summary: str | None = None,
        description: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register *func* for *method* and *path*.

        Parameters are stored to build OpenAPI operations, including optional
        ``summary`` and ``description`` metadata.
        """
        param_names, converters = self._extract_params(path)

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            sig = inspect.signature(func)
            body_param: tuple[str, Any] | None = None
            query_params: List[Tuple[str, Any]] = []
            path_params: List[Tuple[str, Any]] = []
            param_dependencies: List[Tuple[str, Callable[..., Any]]] = []
            route_dependencies: List[Tuple[str, Callable[..., Any]]] = []
            expects_request = False
            background_param: str | None = None
            try:
                type_hints = get_type_hints(func, include_extras=True)
            except Exception:  # noqa: BLE001 - fallback for unresolved hints
                type_hints = {}
            for name, param in sig.parameters.items():
                annotation = type_hints.get(name, param.annotation)
                if annotation is inspect._empty:
                    annotation = param.annotation
                if name in param_names:
                    path_params.append((name, annotation))
                    continue
                if name in {"session", "user"}:
                    if name not in param_names:
                        param_names.append(name)
                    continue
                if name == "request":
                    expects_request = True
                    continue
                if annotation is BackgroundTasks or (
                    isinstance(annotation, str)
                    and annotation == "BackgroundTasks"
                ):
                    background_param = name
                    continue
                default = param.default
                if isinstance(default, Depends):
                    dep_callable = default.dependency
                    if dep_callable is None:
                        dep_callable = _make_dependency_parser(name, annotation)
                    param_dependencies.append((name, dep_callable))
                    continue
                if body_param is None and (
                    name == "payload"
                    or is_dataclass(annotation)
                    or (
                        PydanticBaseModel is not None
                        and inspect.isclass(annotation)
                        and issubclass(annotation, PydanticBaseModel)
                    )
                ):
                    body_param = (name, annotation)
                    continue
                query_params.append((name, annotation))
            if dependencies:
                for i, dep in enumerate(dependencies):
                    if dep.dependency is None:
                        raise TypeError(
                            "Route-level Depends() requires an explicit callable"
                        )
                    route_dependencies.append((f"_dep{i}", dep.dependency))
            expects_body = body_param is not None
            route_info = {
                "method": method,
                "path": path,
                "host": host,
                "func": func,
                "param_names": param_names,
                "param_converters": converters,
                "query_params": query_params,
                "path_params": path_params,
                "body_param": body_param,
                "expects_body": expects_body,
                "dependencies": param_dependencies + route_dependencies,
                "expects_request": expects_request,
                "background_param": background_param,
                "tags": tags or [],
                "responses": responses or {},
                "summary": summary,
                "description": description,
                "dependency_overrides": self.dependency_overrides,
            }
            self.routes.append(route_info)

            if method == "GET" and not any(
                r["path"] == path and r["method"] == "HEAD" and r.get("host") == host
                for r in self.routes
            ):
                head_info = dict(route_info)
                head_info["method"] = "HEAD"
                head_info["expects_body"] = False
                self.routes.append(head_info)
                if self.server is not None:
                    head_handler = self._make_handler(
                        func,
                        param_names,
                        converters,
                        query_params,
                        body_param,
                        param_dependencies + route_dependencies,
                        expects_request,
                        "HEAD",
                        path,
                        background_param,
                    )
                    add_route = getattr(self.server, "add_route")
                    sig = inspect.signature(add_route)
                    if "host" in sig.parameters:
                        add_route(
                            "HEAD",
                            path,
                            lambda b, p, q, hdrs=None, h=head_handler: h(b, p, q, hdrs),
                            host=host,
                        )
                    else:
                        add_route(
                            "HEAD",
                            path,
                            lambda b, p, q, hdrs=None, h=head_handler: h(b, p, q, hdrs),
                        )

            if self.server is not None:
                handler = self._make_handler(
                    func,
                    param_names,
                    converters,
                    query_params,
                    body_param,
                    param_dependencies + route_dependencies,
                    expects_request,
                    method,
                    path,
                    background_param,
                )
                add_route = getattr(self.server, "add_route")
                sig = inspect.signature(add_route)
                if "host" in sig.parameters:
                    add_route(
                        method,
                        path,
                        lambda b, p, q, hdrs=None, h=handler: h(b, p, q, hdrs),
                        host=host,
                    )
                else:
                    add_route(
                        method,
                        path,
                        lambda b, p, q, hdrs=None, h=handler: h(b, p, q, hdrs),
                    )
            self._register_schema_route()
            self._register_metrics_route()
            self._register_docs_routes()
            self._register_observability_routes()
            return func

        return decorator

    def get(
        self,
        path: str,
        host: str | None = None,
        tags: list[str] | None = None,
        responses: dict[int | str, dict[str, Any]] | None = None,
        dependencies: list[Depends] | None = None,
        summary: str | None = None,
        description: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self.route(
            path,
            "GET",
            host=host,
            tags=tags,
            responses=responses,
            dependencies=dependencies,
            summary=summary,
            description=description,
        )

    def post(
        self,
        path: str,
        host: str | None = None,
        tags: list[str] | None = None,
        responses: dict[int | str, dict[str, Any]] | None = None,
        dependencies: list[Depends] | None = None,
        summary: str | None = None,
        description: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self.route(
            path,
            "POST",
            host=host,
            tags=tags,
            responses=responses,
            dependencies=dependencies,
            summary=summary,
            description=description,
        )

    def put(
        self,
        path: str,
        host: str | None = None,
        tags: list[str] | None = None,
        responses: dict[int | str, dict[str, Any]] | None = None,
        dependencies: list[Depends] | None = None,
        summary: str | None = None,
        description: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self.route(
            path,
            "PUT",
            host=host,
            tags=tags,
            responses=responses,
            dependencies=dependencies,
            summary=summary,
            description=description,
        )

    def delete(
        self,
        path: str,
        host: str | None = None,
        tags: list[str] | None = None,
        responses: dict[int | str, dict[str, Any]] | None = None,
        dependencies: list[Depends] | None = None,
        summary: str | None = None,
        description: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self.route(
            path,
            "DELETE",
            host=host,
            tags=tags,
            responses=responses,
            dependencies=dependencies,
            summary=summary,
            description=description,
        )

    def patch(
        self,
        path: str,
        host: str | None = None,
        tags: list[str] | None = None,
        responses: dict[int | str, dict[str, Any]] | None = None,
        dependencies: list[Depends] | None = None,
        summary: str | None = None,
        description: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self.route(
            path,
            "PATCH",
            host=host,
            tags=tags,
            responses=responses,
            dependencies=dependencies,
            summary=summary,
            description=description,
        )

    def head(
        self,
        path: str,
        host: str | None = None,
        tags: list[str] | None = None,
        responses: dict[int | str, dict[str, Any]] | None = None,
        dependencies: list[Depends] | None = None,
        summary: str | None = None,
        description: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self.route(
            path,
            "HEAD",
            host=host,
            tags=tags,
            responses=responses,
            dependencies=dependencies,
            summary=summary,
            description=description,
        )

    def options(
        self,
        path: str,
        host: str | None = None,
        tags: list[str] | None = None,
        responses: dict[int | str, dict[str, Any]] | None = None,
        dependencies: list[Depends] | None = None,
        summary: str | None = None,
        description: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self.route(
            path,
            "OPTIONS",
            host=host,
            tags=tags,
            responses=responses,
            dependencies=dependencies,
            summary=summary,
            description=description,
        )

    def trace(
        self,
        path: str,
        host: str | None = None,
        tags: list[str] | None = None,
        responses: dict[int | str, dict[str, Any]] | None = None,
        dependencies: list[Depends] | None = None,
        summary: str | None = None,
        description: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self.route(
            path,
            "TRACE",
            host=host,
            tags=tags,
            responses=responses,
            dependencies=dependencies,
            summary=summary,
            description=description,
        )

    def graphql(self, path: str, schema: GraphQLSchema) -> None:
        """Register a GraphQL endpoint at ``path`` using ``schema``."""

        if not _GRAPHQL_AVAILABLE:
            raise RuntimeError("graphql-core is not installed")

        @self.post(path)
        def _graphql(payload: dict[str, Any]) -> HTTPResponse:
            query = payload.get("query", "")
            variables = payload.get("variables")
            result = graphql_sync(schema, query, variable_values=variables)
            payload = result.formatted
            return HTTPResponse(json.dumps(payload), media_type="application/json")

        return None

    def graphql_federation(self, path: str, schemas: list[GraphQLSchema]) -> None:
        """Register a federated GraphQL endpoint combining multiple *schemas*."""

        if not _GRAPHQL_AVAILABLE:
            raise RuntimeError("graphql-core is not installed")

        def merge_root(attr: str, name: str) -> GraphQLObjectType | None:
            fields: dict[str, Any] = {}
            for sch in schemas:
                root = getattr(sch, attr)
                if root:
                    fields.update(root.fields)
            return GraphQLObjectType(name=name, fields=fields) if fields else None

        federated = GraphQLSchema(
            query=merge_root("query_type", "Query"),
            mutation=merge_root("mutation_type", "Mutation"),
            subscription=merge_root("subscription_type", "Subscription"),
        )
        self.graphql(path, federated)

    def graphql_subscriptions(self, path: str, schema: GraphQLSchema) -> None:
        """Expose GraphQL subscriptions over WebSockets."""

        if not _GRAPHQL_AVAILABLE:
            raise RuntimeError("graphql-core is not installed")

        @self.websocket(path)
        async def _graphql_ws(ws: WebSocket) -> None:
            await ws.accept()
            payload = json.loads(await ws.receive_text())
            query = payload.get("query", "")
            variables = payload.get("variables")
            result = await subscribe(schema, parse(query), variable_values=variables)
            if isinstance(result, ExecutionResult):
                await ws.send_text(json.dumps(result.formatted, separators=(",", ":")))
            else:
                async for item in result:
                    await ws.send_text(
                        json.dumps(item.formatted, separators=(",", ":"))
                    )
            await ws.close()

        return None

    def websocket(
        self, path: str, host: str | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        param_names, converters = self._extract_params(path)

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.ws_routes.append(
                {
                    "path": path,
                    "host": host,
                    "func": func,
                    "param_names": param_names,
                    "param_converters": converters,
                }
            )
            if self.server is not None and hasattr(
                self.server, "add_ws_route"
            ):  # noqa: E501
                handler = self._make_ws_handler(func, param_names, converters)
                add_ws = getattr(self.server, "add_ws_route")
                sig = inspect.signature(add_ws)
                if "host" in sig.parameters:
                    add_ws(path, handler, host=host)
                else:
                    add_ws(path, handler)
            return func

        return decorator

    def on_event(
        self, event: str
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            if event == "startup":
                self._startup_hooks.append(func)
            elif event == "shutdown":
                self._shutdown_hooks.append(func)
            return func

        return decorator

    async def startup(self) -> None:
        for hook in self._startup_hooks:
            result = hook()
            if inspect.iscoroutine(result):
                await result

    async def shutdown(self) -> None:
        for hook in self._shutdown_hooks:
            result = hook()
            if inspect.iscoroutine(result):
                await result

    def _make_handler(
        self,
        func: Callable[..., Any],
        param_names: List[str],
        converters: Dict[str, Callable[[str], Any]],
        query_params: List[Tuple[str, Any]],
        body_info: bool | tuple[str, Any] | None,
        dependencies: List[Tuple[str, Callable[..., Any]]],
        expects_request: bool = False,
        method: str = "GET",
        path: str = "",
        background_param: str | None = None,
        override_providers: (
            List[Dict[Callable[..., Any], Callable[..., Any]]] | None
        ) = None,
    ) -> Callable[
        [bytes, tuple, bytes, dict[str, str] | None],
        Tuple[int, str | bytes | list[str], dict[str, str]]
        | Awaitable[Tuple[int, str | bytes | list[str], dict[str, str]]],
    ]:
        async def handler_async(
            body: bytes,
            params: tuple,
            query: bytes,
            headers: dict[str, str] | None = None,
        ) -> Tuple[int, str | bytes | list[str], dict[str, str]]:
            start = time.time()
            library_call = headers is None
            headers = headers or {}
            headers_snapshot = dict(headers)
            token = _push_begin()
            collect_metrics = observability_ready()
            if collect_metrics:
                record_metric(
                    "requests_total",
                    get_metric("requests_total") + 1,
                )
            span_label = path or "/"
            span_cm = start_span(span_label)
            span_cm.__enter__()
            span_obj = current_trace_span()
            if span_obj is not None:
                span_obj.set_attribute("http.method", method)
                span_obj.set_attribute("http.route", span_label)
                span_obj.set_attribute("http.request_content_length", len(body))

            finalizer_state: dict[str, Any] = {"invoked": False, "context": None}

            def emit_finalizer(
                status_code: int,
                *,
                duration_ms: float,
                response_length: int | None,
                reason: str = "normal",
                exception: BaseException | None = None,
            ) -> None:
                if finalizer_state.get("invoked"):
                    return
                finalizer_state["invoked"] = True
                context: dict[str, Any] = {
                    "method": method,
                    "route": span_label,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "response_length": response_length,
                    "library_call": library_call,
                    "request_headers": headers_snapshot,
                    "timestamp": start,
                    "error": bool(status_code >= 500),
                    "reason": reason,
                }
                if exception is not None:
                    context["exception"] = repr(exception)
                if span_obj is not None:
                    try:
                        span_context = span_obj.get_span_context()
                        context["span"] = {
                            "trace_id": getattr(span_context, "trace_id", None),
                            "span_id": getattr(span_context, "span_id", None),
                        }
                    except Exception:  # pragma: no cover - best effort telemetry capture
                        pass
                finalizer_state["context"] = context
                notify_telemetry_finalizers(context)
            try:
                def apply_push_headers(
                    status_code: int, headers: dict[str, str] | None
                ) -> dict[str, str]:
                    hdrs = dict(headers or {})
                    pushes = _push_end(token)
                    if pushes:
                        hdrs["link"] = format_link_header(pushes)
                        log_push_hints(pushes, applied_at=time.time())
                    return hdrs

                def finalize_metrics(
                    status_code: int, *, response_length: int | None = None
                ) -> float:
                    duration_ms = (time.time() - start) * 1000
                    if collect_metrics:
                        record_metric("request_duration_ms", duration_ms)
                        record_latency(span_label, duration_ms)
                    if span_obj is not None:
                        span_obj.set_attribute("http.status_code", status_code)
                        span_obj.set_attribute("http.response_time_ms", duration_ms)
                        if response_length is not None:
                            span_obj.set_attribute(
                                "http.response_content_length", response_length
                            )
                        span_obj.set_attribute("forzium.error", bool(status_code >= 500))
                    emit_finalizer(
                        status_code,
                        duration_ms=duration_ms,
                        response_length=response_length,
                    )
                    return duration_ms

                def calculate_body_length(body_obj: Any) -> int | None:
                    if isinstance(body_obj, bytes):
                        return len(body_obj)
                    if isinstance(body_obj, str):
                        return len(body_obj.encode())
                    if isinstance(body_obj, list):
                        total = 0
                        for part in body_obj:
                            if isinstance(part, bytes):
                                total += len(part)
                            elif isinstance(part, str):
                                total += len(part.encode())
                            else:
                                return None
                        return total
                    return None

                def schedule_background(
                    factory: Callable[[], Coroutine[Any, Any, Any]]
                ) -> None:
                    def runner() -> None:
                        # Allow response serialization to complete before running tasks.
                        time.sleep(0.001)
                        asyncio.run(factory())

                    thread = threading.Thread(target=runner, daemon=True)
                    thread.start()

                def finalize_json(
                    status_code: int,
                    payload: Any,
                    resp_headers: dict[str, str] | None = None,
                ) -> tuple[int, str, dict[str, str]]:
                    body_text = json.dumps(payload)
                    hdrs = dict(resp_headers or {})
                    if not library_call:
                        hdrs.setdefault("content-type", "application/json")
                    hdrs = apply_push_headers(status_code, hdrs)
                    finalize_metrics(status_code, response_length=len(body_text.encode()))
                    return status_code, body_text, hdrs

                for req_hook in self._request_hooks:
                    body, params, query, resp = req_hook(body, params, query)
                    if resp is not None:
                        status, body_obj, hook_headers = resp
                        for resp_hook in self._response_hooks:
                            status, body_obj, hook_headers = resp_hook(
                                status, body_obj, hook_headers
                            )
                        hook_headers = apply_push_headers(status, hook_headers)
                        finalize_metrics(
                            status,
                            response_length=calculate_body_length(body_obj),
                        )
                        return status, body_obj, hook_headers

                kwargs = {}
                for name, value in zip(param_names, params):
                    conv = converters.get(name)
                    kwargs[name] = conv(value) if conv else value
                bg_tasks = (
                    BackgroundTasks(queue=self.task_queue)
                    if background_param
                    else None
                )
                if background_param:
                    kwargs[background_param] = bg_tasks
                url = path
                if query:
                    url += "?" + query.decode()
                req_obj = Request(
                    method=method,
                    url=url,
                    body=body,
                    headers=headers,
                    path_params={name: val for name, val in zip(param_names, params)},
                    max_upload_size=self.max_upload_size,
                    allowed_mime_types=self.allowed_mime_types,
                )
                req_obj.state.route = path
                request_id = headers.get("x-request-id") if headers else None
                if request_id:
                    req_obj.state.request_id = request_id
                if span_obj is not None:
                    span_obj.set_attribute("http.target", url)
                if expects_request:
                    kwargs["request"] = req_obj
                overrides = override_providers or [self.dependency_overrides]
                ctx_stack: list[tuple[Callable[[], Any], bool]] = []
                dep_vals: dict[str, Any] = {}
                try:
                    with start_span(f"{span_label} dependency_resolution"):
                        dep_vals, ctx_stack = await solve_dependencies(
                            dependencies, overrides, req_obj
                        )
                except Exception as exc:
                    handler = self._lookup_handler(exc)
                    if handler:
                        custom = handler(req_obj, exc)
                        if isinstance(custom, HTTPResponse):
                            body_val = custom.body
                            body_str = (
                                json.dumps(body_val)
                                if isinstance(body_val, (dict, list))
                                else str(body_val)
                            )
                            headers_val = dict(custom.headers)
                            headers_val = apply_push_headers(
                                custom.status_code, headers_val
                            )
                            finalize_metrics(
                                custom.status_code,
                                response_length=len(body_str.encode()),
                            )
                            return custom.status_code, body_str, headers_val
                        if isinstance(custom, tuple):
                            status_c, body_val, headers_c = custom
                            body_str = (
                                json.dumps(body_val)
                                if isinstance(body_val, (dict, list))
                                else str(body_val)
                            )
                            headers_c = apply_push_headers(status_c, headers_c)
                            finalize_metrics(
                                status_c, response_length=len(body_str.encode())
                            )
                            return status_c, body_str, headers_c
                    if isinstance(exc, HTTPException):
                        return finalize_json(
                            exc.status_code,
                            {"detail": exc.detail},
                            dict(exc.headers),
                        )
                    if isinstance(exc, DependencyValidationError):
                        return finalize_json(
                            422, {"detail": exc.errors()}, {}
                        )
                    if isinstance(exc, ValueError):
                        return finalize_json(
                            400, {"detail": str(exc)}, {}
                        )
                    return finalize_json(
                        500, {"detail": "Internal Server Error"}, {}
                    )
                
                for name, val in dep_vals.items():
                    if not name.startswith("_dep"):
                        kwargs[name] = val
                if query and query_params:
                    with start_span(f"{span_label} query_validation"):
                        parsed = parse_qs(query.decode())
                        for name, anno in query_params:
                            if name in parsed:
                                raw = parsed[name][0]
                                try:
                                    kwargs[name] = _coerce_value(
                                        raw, anno, ["query", name]
                                    )
                                except Exception as exc:  # noqa: BLE001
                                    if (
                                        PydanticValidationError is not None
                                        and isinstance(exc, PydanticValidationError)
                                    ):
                                        errors = exc.errors()
                                        for err in errors:
                                            err.pop("url", None)
                                            err["loc"] = [
                                                "query",
                                                name,
                                                *err.get("loc", []),
                                            ]
                                        return finalize_json(
                                            422, {"detail": errors}, {}
                                        )
                                    if isinstance(exc, RequestValidationError):
                                        return finalize_json(
                                            422,
                                            {"detail": exc.errors()},
                                            {},
                                        )
                                    if isinstance(exc, ValueError):
                                        detail = {
                                            "loc": ["query", name],
                                            "msg": str(exc),
                                            "type": "value_error",
                                            "input": raw,
                                        }
                                        return finalize_json(
                                            422, {"detail": [detail]}, {}
                                        )
                                    raise
                if isinstance(body_info, tuple):
                    payload = json.loads(body.decode()) if body else {}
                    name, anno = body_info
                    with start_span(f"{span_label} body_validation"):
                        try:
                            kwargs[name] = _coerce_value(
                                payload, anno, ["body"]
                            )
                        except Exception as exc:  # noqa: BLE001
                            if (
                                PydanticValidationError is not None
                                and isinstance(exc, PydanticValidationError)
                            ):
                                errors = exc.errors()
                                for err in errors:
                                    err.pop("url", None)
                                    err_loc = list(err.get("loc", []))
                                    if not err_loc:
                                        err_loc = ["body"]
                                    elif err_loc[0] != "body":
                                        err_loc = ["body", *err_loc]
                                    err["loc"] = err_loc
                                return finalize_json(
                                    422, {"detail": errors}, {}
                                )
                            if isinstance(exc, RequestValidationError):
                                return finalize_json(
                                    422,
                                    {"detail": exc.errors()},
                                    {},
                                )
                            if isinstance(exc, ValueError):
                                detail = {
                                    "loc": ["body", name],
                                    "msg": str(exc),
                                    "type": "value_error",
                                    "input": payload,
                                }
                                return finalize_json(
                                    422, {"detail": [detail]}, {}
                                )
                            raise
                elif body_info:
                    payload = json.loads(body.decode()) if body else {}
                    kwargs["payload"] = payload
                try:
                    with start_span(f"{span_label} handler_execution"):
                        result = func(**kwargs)
                        if inspect.isawaitable(result):
                            result = await cast(
                                Coroutine[Any, Any, Any], result
                            )
                except Exception as exc:
                    handler = self._lookup_handler(exc)
                    if handler:
                        custom = handler(req_obj, exc)
                        if isinstance(custom, HTTPResponse):
                            body_val = custom.body
                            body_str = (
                                json.dumps(body_val)
                                if isinstance(body_val, (dict, list))
                                else str(body_val)
                            )
                            headers_val = dict(custom.headers)
                            headers_val = apply_push_headers(
                                custom.status_code, headers_val
                            )
                            finalize_metrics(
                                custom.status_code,
                                response_length=len(body_str.encode()),
                            )
                            return custom.status_code, body_str, headers_val
                        if isinstance(custom, tuple):
                            status_c, body_val, headers_c = custom
                            body_str = (
                                json.dumps(body_val)
                                if isinstance(body_val, (dict, list))
                                else str(body_val)
                            )
                            headers_c = apply_push_headers(status_c, headers_c)
                            finalize_metrics(
                                status_c, response_length=len(body_str.encode())
                            )
                            return status_c, body_str, headers_c
                    if isinstance(exc, HTTPException):
                        return finalize_json(
                            exc.status_code,
                            {"detail": exc.detail},
                            dict(exc.headers),
                        )
                    if isinstance(exc, ValueError):
                        return finalize_json(
                            400, {"detail": str(exc)}, {}
                        )
                    return finalize_json(
                        500, {"detail": "Internal Server Error"}, {}
                    )
                finally:
                    for cleanup, is_async in reversed(ctx_stack):
                        if is_async:
                            await cast(Awaitable[Any], cleanup())
                        else:
                            cleanup()

                if isinstance(result, StreamingResponse):
                    if bg_tasks and bg_tasks.tasks:
                        if result.background is None:
                            result.background = bg_tasks
                        elif isinstance(result.background, BackgroundTasks):
                            result.background.tasks.extend(bg_tasks.tasks)
                        else:
                            result.background = BackgroundTasks(
                                [result.background, *bg_tasks.tasks],
                                queue=self.task_queue,
                            )
                    res_headers = dict(result.headers)
                    try:
                        raw_chunks = list(result.body_iter())
                    except HTTPException as exc:
                        return finalize_json(
                            exc.status_code,
                            {"detail": exc.detail},
                            dict(exc.headers),
                        )
                    except ValueError as exc:
                        return finalize_json(400, {"detail": str(exc)}, {})
                    except Exception:
                        return finalize_json(
                            500, {"detail": "Internal Server Error"}, {}
                        )
                    chunks: list[str] = []
                    total_length = 0
                    for chunk in raw_chunks:
                        if isinstance(chunk, bytes):
                            text = chunk.decode("latin1")
                        else:
                            text = str(chunk)
                        chunks.append(text)
                        total_length += len(text)
                    res_headers = apply_push_headers(
                        result.status_code, res_headers
                    )
                    finalize_metrics(
                        result.status_code,
                        response_length=total_length,
                    )
                    if result.background is not None:
                        schedule_background(
                            lambda: cast(
                                Coroutine[Any, Any, Any],
                                result.run_background(),
                            )
                        )
                    if method == "HEAD":
                        return result.status_code, [], res_headers
                    return result.status_code, chunks, res_headers
                if isinstance(result, HTTPResponse):
                    if bg_tasks and bg_tasks.tasks:
                        if result.background is None:
                            result.background = bg_tasks
                        elif isinstance(result.background, BackgroundTasks):
                            result.background.tasks.extend(bg_tasks.tasks)
                        else:
                            result.background = BackgroundTasks(
                                [result.background, *bg_tasks.tasks],
                                queue=self.task_queue,
                            )
                    status, body_bytes, res_headers = result.serialize()
                    body_view: str | bytes = body_bytes.decode("latin1")
                    for resp_hook in self._response_hooks:
                        status, body_view, res_headers = resp_hook(
                            status, body_view, res_headers
                        )
                    res_headers = apply_push_headers(status, res_headers)
                    if isinstance(body_view, bytes):
                        final_body = body_view
                    else:
                        try:
                            final_body = body_view.encode("latin1")
                        except UnicodeEncodeError:
                            final_body = body_view.encode()
                    finalize_metrics(
                        status, response_length=len(final_body)
                    )
                    if result.background is not None:
                        schedule_background(
                            lambda: cast(
                                Coroutine[Any, Any, Any],
                                result.run_background(),
                            )
                        )
                    if method == "HEAD":
                        return status, b"", res_headers
                    return status, final_body, res_headers
                status = 200
                resp_headers: dict[str, str] = {}
                if (
                    isinstance(result, tuple)
                    and len(result) == 2
                    and isinstance(result[0], int)
                ):
                    status, data = result
                else:
                    data = result
                accept = req_obj.headers.get("accept")
                media = self._choose_media(accept)
                if accept and media is None:
                    headers = apply_push_headers(406, {})
                    finalize_metrics(406, response_length=0)
                    return 406, "", headers
                if media is None:
                    if isinstance(data, (dict, list)):
                        media = "application/json"
                    else:
                        media = "text/plain"
                if media == "text/plain":
                    body_str = str(data)
                    if not library_call:
                        resp_headers["content-type"] = "text/plain; charset=utf-8"
                elif media == "application/json":
                    body_str = json.dumps(data)
                    if not library_call:
                        resp_headers["content-type"] = "application/json"
                else:
                    body_str = (
                        json.dumps(data)
                        if isinstance(data, (dict, list))
                        else str(data)
                    )
                    if media and not library_call:
                        resp_headers["content-type"] = media
                for resp_hook in self._response_hooks:
                    status, body_str, resp_headers = resp_hook(
                        status, body_str, resp_headers
                    )
                resp_headers = apply_push_headers(status, resp_headers)
                finalize_metrics(status, response_length=len(body_str.encode()))
                if method == "HEAD":
                    return status, "", resp_headers
                return status, body_str, resp_headers
            finally:
                exc_info = sys.exc_info()
                if not finalizer_state.get("invoked"):
                    emit_finalizer(
                        500,
                        duration_ms=(time.time() - start) * 1000,
                        response_length=None,
                        reason="unhandled_exception",
                        exception=exc_info[1],
                    )
                span_cm.__exit__(*exc_info)
        
        def handler(
            body: bytes,
            params: tuple,
            query: bytes,
            headers: dict[str, str] | None = None,
        ) -> Tuple[int, str | bytes | list[str], dict[str, str]] | Awaitable[
            Tuple[int, str | bytes | list[str], dict[str, str]]
        ]:
            coro = handler_async(body, params, query, headers)
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                # No running loop, execute coroutine synchronously.
                return asyncio.run(coro)
            # Reuse the active loop by scheduling the coroutine as a task.
            return asyncio.create_task(coro)

        handler = self._apply_asgi_middleware(
            handler, param_names, method, path
        )  # type: ignore[assignment]
        return handler

    def _apply_asgi_middleware(
        self,
        handler: Callable[
            [bytes, tuple, bytes, dict[str, str] | None],
            tuple[int, str | list[str], dict[str, str]],
        ],
        param_names: List[str],
        method: str,
        path: str,
    ) -> Callable[
        [bytes, tuple, bytes, dict[str, str] | None],
        tuple[int, str | list[str], dict[str, str]],
    ]:
        if not self._asgi_middleware:
            return handler

        def wrap(mw: Callable, nxt: Callable):
            def wrapped(
                body: bytes,
                params: tuple,
                query: bytes,
                headers: dict[str, str] | None = None,
            ):
                url = path + ("?" + query.decode() if query else "")
                req = Request(
                    method=method,
                    url=url,
                    body=body,
                    headers=headers or {},
                    path_params={n: v for n, v in zip(param_names, params)},
                    max_upload_size=self.max_upload_size,
                    allowed_mime_types=self.allowed_mime_types,
                )
                req.state.route = path
                request_id = req.headers.get("x-request-id")
                if request_id:
                    req.state.request_id = request_id

                def call_next_sync(r: Request) -> HTTPResponse:
                    q = r.url.split("?", 1)[1] if "?" in r.url else ""
                    st, bd, hd = nxt(r._body, params, q.encode(), r.headers)
                    return HTTPResponse(bd, status_code=st, headers=hd)

                async def call_next_async(r: Request) -> HTTPResponse:
                    q = r.url.split("?", 1)[1] if "?" in r.url else ""
                    result = nxt(r._body, params, q.encode(), r.headers)
                    if inspect.iscoroutine(result):
                        result = await result
                    if isinstance(result, HTTPResponse):
                        return result
                    st, bd, hd = result
                    return HTTPResponse(bd, status_code=st, headers=hd)

                call_next = (
                    call_next_async
                    if inspect.iscoroutinefunction(mw)
                    else call_next_sync
                )

                res = mw(req, call_next)
                if inspect.isawaitable(res):
                    try:
                        asyncio.get_running_loop()
                    except RuntimeError:
                        res = asyncio.run(cast(Coroutine[Any, Any, Any], res))
                    else:
                        if isinstance(res, asyncio.Task):
                            return res
                        if inspect.iscoroutine(res):
                            return asyncio.create_task(
                                cast(Coroutine[Any, Any, Any], res)
                            )
                        return asyncio.ensure_future(cast(Awaitable[Any], res))
                if isinstance(res, HTTPResponse):
                    st, b, hd = res.serialize()
                    return st, b.decode("latin1"), hd
                return res

            return wrapped

        h = handler
        for mw in reversed(self._asgi_middleware):
            h = wrap(mw, h)
        return h

    def _make_ws_handler(
        self,
        func: Callable[..., Any],
        param_names: List[str],
        converters: Dict[str, Callable[[str], Any]],
    ) -> Callable[[WebSocket, tuple], Any]:
        async def handler(ws: WebSocket, params: tuple) -> None:
            if observability_ready():
                prev = get_metric("websocket_connections_total")
                record_metric("websocket_connections_total", prev + 1)
            kwargs = {}
            for name, value in zip(param_names, params):
                conv = converters.get(name)
                kwargs[name] = conv(value) if conv else value
            await func(ws, **kwargs)

        return handler

    def add_request_middleware(
        self,
        func: Callable[[bytes, tuple, bytes], tuple[bytes, tuple, bytes]],
    ) -> None:
        """Register a hook executed before each request."""

        def wrapper(body: bytes, params: tuple, query: bytes):
            b, p, q = func(body, params, query)
            return b, p, q, None

        self._request_hooks.append(wrapper)

    def add_response_middleware(
        self,
        func: Callable[[int, str], tuple[int, str]],
    ) -> None:
        """Register a hook executed after each response."""

        def wrapper(status: int, body: str, headers: dict[str, str]):
            st, bd = func(status, body)
            return st, bd, headers

        self._response_hooks.append(wrapper)

    def add_middleware(self, middleware_cls: type, **options: Any) -> None:
        """Attach *middleware_cls* to the application."""
        middleware = middleware_cls(**options)
        if hasattr(middleware, "before_request"):
            self._request_hooks.append(middleware.before_request)
        if hasattr(middleware, "after_response"):
            self._response_hooks.insert(0, middleware.after_response)

    def middleware(self, typ: str) -> Callable[[Callable], Callable]:
        """Register ASGI-style *typ* middleware."""
        if typ != "http":
            raise ValueError("only http middleware supported")

        def decorator(func: Callable) -> Callable:
            self._asgi_middleware.append(func)
            return func

        return decorator

    def include_router(
        self,
        router: "ForziumApp",
        prefix: str = "",
        host: str | None = None,
        tags: list[str] | None = None,
        responses: dict[int | str, dict[str, Any]] | None = None,
        dependencies: list[Depends] | None = None,
    ) -> None:
        """Attach routes from *router* under *prefix* with *tags*."""
        self._startup_hooks.extend(router._startup_hooks)
        self._shutdown_hooks.extend(router._shutdown_hooks)
        self._request_hooks.extend(router._request_hooks)
        self._response_hooks.extend(router._response_hooks)
        self.security_schemes.update(router.security_schemes)
        extra_deps: list[Tuple[str, Callable[..., Any]]] = []
        if dependencies:
            for i, dep in enumerate(dependencies):
                extra_deps.append((f"_depinc{i}", dep.dependency))
        for route in router.routes:
            if route["path"] == "/openapi.json":
                continue
            if route["path"] in {"/docs", "/redoc", "/metrics"}:
                path = route["path"]
            else:
                path = prefix + route["path"]
            rhost = host or route.get("host")
            route_tags = list(dict.fromkeys(route.get("tags", []) + (tags or [])))
            if self.server is not None:
                handler = self._make_handler(
                    route["func"],
                    route["param_names"],
                    route["param_converters"],
                    route["query_params"],
                    route.get("body_param"),
                    route["dependencies"] + extra_deps,
                    route.get("expects_request", False),
                    route["method"],
                    path,
                    route.get("background_param"),
                    [router.dependency_overrides, self.dependency_overrides],
                )
                add_route = getattr(self.server, "add_route")
                sig = inspect.signature(add_route)

                def wrapper(body, params, query, headers=None, h=handler):
                    return h(body, params, query, headers)

                kwargs = {"host": rhost} if "host" in sig.parameters else {}
                add_route(route["method"], path, wrapper, **kwargs)
            merged_responses = {
                **route.get("responses", {}),
                **(responses or {}),
            }
            self.routes.append(
                {
                    "path": path,
                    "method": route["method"],
                    "func": route["func"],
                    "param_names": route["param_names"],
                    "param_converters": route["param_converters"],
                    "query_params": route["query_params"],
                    "path_params": route.get("path_params", []),
                    "body_param": route.get("body_param"),
                    "expects_body": route.get("body_param") is not None,
                    "dependencies": route["dependencies"] + extra_deps,
                    "expects_request": route.get("expects_request", False),
                    "background_param": route.get("background_param"),
                    "host": rhost,
                    "tags": route_tags,
                    "responses": merged_responses,
                    "summary": route.get("summary"),
                    "description": route.get("description"),
                    "dependency_overrides": router.dependency_overrides,
                }
            )
        self._register_schema_route()

    def mount(self, prefix: str, app: "ForziumApp") -> None:
        """Mount a sub-application at *prefix* with isolated overrides."""

        self._startup_hooks.extend(app._startup_hooks)
        self._shutdown_hooks.extend(app._shutdown_hooks)
        for route in app.routes:
            if route["path"] == "/openapi.json":
                continue
            full_path = prefix.rstrip("/") + route["path"]
            if self.server is not None:
                handler = app._make_handler(
                    route["func"],
                    route["param_names"],
                    route["param_converters"],
                    route["query_params"],
                    route.get("body_param"),
                    route["dependencies"],
                    route.get("expects_request", False),
                    route["method"],
                    full_path,
                    route.get("background_param"),
                    [app.dependency_overrides],
                )
                add_route = getattr(self.server, "add_route")
                sig = inspect.signature(add_route)

                def wrapper(body, params, query, headers=None, h=handler):
                    return h(body, params, query, headers)

                kwargs = {"host": route.get("host")} if "host" in sig.parameters else {}
                add_route(route["method"], full_path, wrapper, **kwargs)
            self.routes.append(
                {
                    "path": full_path,
                    "method": route["method"],
                    "func": route["func"],
                    "param_names": route["param_names"],
                    "param_converters": route["param_converters"],
                    "query_params": route["query_params"],
                    "path_params": route.get("path_params", []),
                    "body_param": route.get("body_param"),
                    "expects_body": route.get("body_param") is not None,
                    "dependencies": route["dependencies"],
                    "expects_request": route.get("expects_request", False),
                    "background_param": route.get("background_param"),
                    "host": route.get("host"),
                    "tags": route.get("tags"),
                    "responses": route.get("responses"),
                    "summary": route.get("summary"),
                    "description": route.get("description"),
                    "dependency_overrides": app.dependency_overrides,
                    "app": app,
                    "use_parent_overrides": False,
                }
            )