"""Decorator-based routing tied directly to the Rust server."""

import asyncio
import inspect
import json
import re
import threading
import time
from dataclasses import MISSING, fields, is_dataclass
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Tuple,
    get_args,
    get_origin,
)
from urllib.parse import parse_qs

from infrastructure.monitoring import get_metric, prometheus_metrics, record_metric

from .dependency import (
    BackgroundTasks,
    Depends,
    Request,
    Response as HTTPResponse,
)
from .http2 import _begin as _push_begin
from .http2 import _end as _push_end
from .websockets import WebSocket


class ForziumApp:
    """Register Python handlers with the Rust HTTP server."""

    def __init__(self, server: Any | None = None) -> None:
        self.server = server
        self.routes: list[dict[str, Any]] = []
        self.ws_routes: list[dict[str, Any]] = []
        self._request_hooks: list[
            Callable[
                [bytes, tuple, bytes],
                tuple[bytes, tuple, bytes, tuple[int, str, dict[str, str]] | None],
            ]
        ] = []
        self._response_hooks: list[
            Callable[[int, str, dict[str, str]], tuple[int, str, dict[str, str]]]
        ] = []
        self._asgi_middleware: list[
            Callable[[Request, Callable[[Request], HTTPResponse]], HTTPResponse]
        ] = []
        self._startup_hooks: list[Callable[[], Any]] = []
        self._shutdown_hooks: list[Callable[[], Any]] = []
        self._schema_route_registered = False
        self._metrics_route_registered = False
        self._docs_route_registered = False
        self.security_schemes: dict[str, Any] = {}
        self.dependency_overrides: dict[Callable[..., Any], Callable[..., Any]] = {}

    def add_security_scheme(self, name: str, scheme: dict[str, Any]) -> None:
        """Register security *scheme* under *name*."""

        self.security_schemes[name] = scheme

    def openapi_schema(self) -> dict[str, Any]:
        """Generate an OpenAPI document for the registered routes."""

        paths: dict[str, dict[str, dict[str, Any]]] = {}
        components: dict[str, dict[str, Any]] = {
            "schemas": {},
            "securitySchemes": self.security_schemes,
        }
        tag_set: set[str] = set()

        def type_schema(tp: Any) -> dict[str, Any]:
            origin = get_origin(tp)
            if is_dataclass(tp):
                name = tp.__name__
                if name not in components["schemas"]:
                    props: dict[str, Any] = {}
                    required: list[str] = []
                    for f in fields(tp):
                        props[f.name] = type_schema(f.type)
                        if (
                            f.default is MISSING
                            and f.default_factory is MISSING
                        ):
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

        paths: dict[str, dict[str, dict[str, Any]]] = {}
        for route in self.routes:
            op: dict[str, Any] = {"responses": {"200": {"description": "OK"}}}
            ret = inspect.signature(route["func"]).return_annotation
            op["responses"]["200"]["content"] = {
                "application/json": {"schema": type_schema(ret)}
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
                "expects_body": False,
                "dependencies": [],
                "expects_request": False,
            }
        )
        if self.server is not None:
            handler = self._make_handler(
                _schema, [], {}, [], False, [], False, "GET", "/openapi.json"
            )
            add_route = getattr(self.server, "add_route")
            sig = inspect.signature(add_route)
            if "host" in sig.parameters:
                add_route(
                    "GET",
                    "/openapi.json",
                    lambda b, p, q, h=handler: h(b, p, q)[:2],
                    host=None,
                )
            else:
                add_route(
                    "GET",
                    "/openapi.json",
                    lambda b, p, q, h=handler: h(b, p, q)[:2],
                )

    def _register_metrics_route(self) -> None:
        if self._metrics_route_registered:
            return
        self._metrics_route_registered = True

        def _metrics() -> str:
            return prometheus_metrics()

        self.routes.append(
            {
                "method": "GET",
                "path": "/metrics",
                "host": None,
                "func": _metrics,
                "param_names": [],
                "param_converters": {},
                "query_params": [],
                "expects_body": False,
                "dependencies": [],
                "expects_request": False,
            }
        )
        if self.server is not None:
            handler = self._make_handler(
                _metrics, [], {}, [], False, [], False, "GET", "/metrics"
            )
            add_route = getattr(self.server, "add_route")
            sig = inspect.signature(add_route)
            if "host" in sig.parameters:
                add_route(
                    "GET",
                    "/metrics",
                    lambda b, p, q, h=handler: h(b, p, q)[:2],
                    host=None,
                )
            else:
                add_route(
                    "GET",
                    "/metrics",
                    lambda b, p, q, h=handler: h(b, p, q)[:2],
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
                    "expects_body": False,
                    "dependencies": [],
                    "expects_request": False,
                }
            )
            if self.server is not None:
                handler = self._make_handler(
                    func, [], {}, [], False, [], False, "GET", path
                )
                add_route = getattr(self.server, "add_route")
                sig = inspect.signature(add_route)
                if "host" in sig.parameters:
                    add_route(
                        "GET",
                        path,
                        lambda b, p, q, h=handler: h(b, p, q)[:2],
                        host=None,
                    )
                else:
                    add_route(
                        "GET",
                        path,
                        lambda b, p, q, h=handler: h(b, p, q)[:2],
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
        return names, convs

    def route(
        self,
        path: str,
        method: str,
        host: str | None = None,
        tags: list[str] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register *func* for *method* and *path*."""
        param_names, converters = self._extract_params(path)

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            sig = inspect.signature(func)
            expects_body = "payload" in sig.parameters
            query_params: List[Tuple[str, Any]] = []
            dependencies: List[Tuple[str, Callable[..., Any]]] = []
            expects_request = False
            background_param: str | None = None
            for name, param in sig.parameters.items():
                if name in param_names or name == "payload":
                    continue
                if name == "session":
                    param_names.append(name)
                    continue
                if name == "request":
                    expects_request = True
                    continue
                if param.annotation is BackgroundTasks or (
                    isinstance(param.annotation, str)
                    and param.annotation == "BackgroundTasks"
                ):
                    background_param = name
                    continue
                default = param.default
                if isinstance(default, Depends):
                    dependencies.append((name, default.dependency))
                else:
                    query_params.append((name, param.annotation))
            self.routes.append(
                {
                    "method": method,
                    "path": path,
                    "host": host,
                    "func": func,
                    "param_names": param_names,
                    "param_converters": converters,
                    "query_params": query_params,
                    "expects_body": expects_body,
                    "dependencies": dependencies,
                    "expects_request": expects_request,
                    "background_param": background_param,
                    "tags": tags or [],
                    "dependency_overrides": self.dependency_overrides,
                }
            )
            if self.server is not None:
                handler = self._make_handler(
                    func,
                    param_names,
                    converters,
                    query_params,
                    expects_body,
                    dependencies,
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
                        lambda b, p, q, h=handler: h(b, p, q)[:2],
                        host=host,
                    )
                else:
                    add_route(
                        method,
                        path,
                        lambda b, p, q, h=handler: h(b, p, q)[:2],
                    )
            self._register_schema_route()
            self._register_metrics_route()
            self._register_docs_routes()
            return func

        return decorator

    def get(
        self,
        path: str,
        host: str | None = None,
        tags: list[str] | None = None,
    ):
        return self.route(path, "GET", host=host, tags=tags)

    def post(
        self,
        path: str,
        host: str | None = None,
        tags: list[str] | None = None,
    ):
        return self.route(path, "POST", host=host, tags=tags)

    def put(
        self,
        path: str,
        host: str | None = None,
        tags: list[str] | None = None,
    ):
        return self.route(path, "PUT", host=host, tags=tags)

    def delete(
        self,
        path: str,
        host: str | None = None,
        tags: list[str] | None = None,
    ):
        return self.route(path, "DELETE", host=host, tags=tags)

    def patch(
        self,
        path: str,
        host: str | None = None,
        tags: list[str] | None = None,
    ):
        return self.route(path, "PATCH", host=host, tags=tags)

    def head(
        self,
        path: str,
        host: str | None = None,
        tags: list[str] | None = None,
    ):
        return self.route(path, "HEAD", host=host, tags=tags)

    def options(
        self,
        path: str,
        host: str | None = None,
        tags: list[str] | None = None,
    ):
        return self.route(path, "OPTIONS", host=host, tags=tags)

    def trace(
        self,
        path: str,
        host: str | None = None,
        tags: list[str] | None = None,
    ):
        return self.route(path, "TRACE", host=host, tags=tags)

    def websocket(self, path: str, host: str | None = None):
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
            if self.server is not None and hasattr(self.server, "add_ws_route"):
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
        expects_body: bool,
        dependencies: List[Tuple[str, Callable[..., Any]]],
        expects_request: bool = False,
        method: str = "GET",
        path: str = "",
        background_param: str | None = None,
        override_providers: List[
            Dict[Callable[..., Any], Callable[..., Any]]
        ] | None = None,
    ) -> Callable[[bytes, tuple, bytes], Tuple[int, str, dict[str, str]]]:
        def handler(
            body: bytes, params: tuple, query: bytes
        ) -> Tuple[int, str, dict[str, str]]:
            start = time.time()
            token = _push_begin()
            record_metric(
                "requests_total",
                get_metric("requests_total") + 1,
            )
            for hook in self._request_hooks:
                body, params, query, resp = hook(body, params, query)
                if resp is not None:
                    status, body_str, headers = resp
                    for rhook in self._response_hooks:
                        status, body_str, headers = rhook(status, body_str, headers)
                    pushes = _push_end(token)
                    if pushes:
                        headers = dict(headers)
                        headers["link"] = ", ".join(
                            f"<{p}>; rel=preload" for p in pushes
                        )
                    duration = (time.time() - start) * 1000
                    record_metric("request_duration_ms", duration)
                    return status, body_str, headers
            kwargs = {}
            for name, value in zip(param_names, params):
                conv = converters.get(name)
                kwargs[name] = conv(value) if conv else value
            bg_tasks = BackgroundTasks() if background_param else None
            if background_param:
                kwargs[background_param] = bg_tasks
            if expects_request:
                url = path
                if query:
                    url += "?" + query.decode()
                kwargs["request"] = Request(
                    method=method,
                    url=url,
                    body=body,
                    headers={},
                    path_params={name: val for name, val in zip(param_names, params)},
                )
            ctx_stack: list[tuple[Any, bool]] = []
            overrides = override_providers or [self.dependency_overrides]
            for name, dep in dependencies:
                dep_fn = dep
                for mapping in overrides:
                    if dep in mapping:
                        dep_fn = mapping[dep]
                dep_val = dep_fn()
                if inspect.isawaitable(dep_val):
                    dep_val = asyncio.run(dep_val)
                elif hasattr(dep_val, "__aenter__") and hasattr(dep_val, "__aexit__"):
                    cm = dep_val
                    dep_val = asyncio.run(cm.__aenter__())
                    ctx_stack.append((cm, True))
                elif hasattr(dep_val, "__enter__") and hasattr(dep_val, "__exit__"):
                    cm = dep_val
                    dep_val = cm.__enter__()
                    ctx_stack.append((cm, False))
                kwargs[name] = dep_val
            if query:
                parsed = parse_qs(query.decode())
                for name, anno in query_params:
                    if name in parsed:
                        raw = parsed[name][0]
                        kwargs[name] = int(raw) if anno is int else raw
            if expects_body:
                payload = json.loads(body.decode()) if body else {}
                kwargs["payload"] = payload
            try:
                result = func(**kwargs)
            except ValueError as exc:
                return 400, json.dumps({"detail": str(exc)}), {}
            finally:
                for cm, is_async in reversed(ctx_stack):
                    if is_async:
                        asyncio.run(cm.__aexit__(None, None, None))
                    else:
                        cm.__exit__(None, None, None)
            if isinstance(result, HTTPResponse):
                if bg_tasks and bg_tasks.tasks:
                    if result.background is None:
                        result.background = bg_tasks
                    elif isinstance(result.background, BackgroundTasks):
                        result.background.tasks.extend(bg_tasks.tasks)
                    else:
                        result.background = BackgroundTasks(
                            [result.background, *bg_tasks.tasks]
                        )
                status, body_bytes, headers = result.serialize()
                body_str = body_bytes.decode("latin1")
                for hook in self._response_hooks:
                    status, body_str, headers = hook(status, body_str, headers)
                pushes = _push_end(token)
                if pushes:
                    headers["link"] = ", ".join(
                        f"<{p}>; rel=preload" for p in pushes
                    )
                duration = (time.time() - start) * 1000
                record_metric("request_duration_ms", duration)
                if result.background is not None:
                    threading.Thread(
                        target=lambda: asyncio.run(result.run_background())
                    ).start()
                return status, body_str, headers
            status = 200
            headers: dict[str, str] = {}
            if (
                isinstance(result, tuple)
                and len(result) == 2
                and isinstance(result[0], int)
            ):
                status, data = result
            else:
                data = result
            body_str = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
            for hook in self._response_hooks:
                status, body_str, headers = hook(status, body_str, headers)
            pushes = _push_end(token)
            if pushes:
                headers["link"] = ", ".join(f"<{p}>; rel=preload" for p in pushes)
            duration = (time.time() - start) * 1000
            record_metric("request_duration_ms", duration)
            return status, body_str, headers
        handler = self._apply_asgi_middleware(
            handler, param_names, method, path
        )
        return handler
    
    def _apply_asgi_middleware(
        self,
        handler: Callable[[bytes, tuple, bytes], tuple[int, str, dict[str, str]]],
        param_names: List[str],
        method: str,
        path: str,
    ) -> Callable[[bytes, tuple, bytes], tuple[int, str, dict[str, str]]]:
        if not self._asgi_middleware:
            return handler

        def wrap(mw: Callable, nxt: Callable):
            def wrapped(body: bytes, params: tuple, query: bytes):
                url = path + ("?" + query.decode() if query else "")
                req = Request(
                    method=method,
                    url=url,
                    body=body,
                    headers={},
                    path_params={n: v for n, v in zip(param_names, params)},
                )

                def call_next_sync(r: Request) -> HTTPResponse:
                    q = r.url.split("?", 1)[1] if "?" in r.url else ""
                    st, bd, hd = nxt(r._body, params, q.encode())
                    return HTTPResponse(bd, status_code=st, headers=hd)

                async def call_next_async(r: Request) -> HTTPResponse:
                    q = r.url.split("?", 1)[1] if "?" in r.url else ""
                    result = nxt(r._body, params, q.encode())
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
                if inspect.iscoroutine(res):
                    try:
                        asyncio.get_running_loop()
                        return res
                    except RuntimeError:
                        res = asyncio.run(res)
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
    ) -> None:
        """Attach routes from *router* under *prefix* with *tags*."""
        self._startup_hooks.extend(router._startup_hooks)
        self._shutdown_hooks.extend(router._shutdown_hooks)
        self._request_hooks.extend(router._request_hooks)
        self._response_hooks.extend(router._response_hooks)
        self.security_schemes.update(router.security_schemes)
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
                    route["expects_body"],
                    route["dependencies"],
                    route.get("expects_request", False),
                    route["method"],
                    path,
                    route.get("background_param"),
                    [router.dependency_overrides, self.dependency_overrides],
                )
                add_route = getattr(self.server, "add_route")
                sig = inspect.signature(add_route)
                wrapper = lambda b, p, q, h=handler: h(b, p, q)[:2]
                kwargs = {"host": rhost} if "host" in sig.parameters else {}
                add_route(route["method"], path, wrapper, **kwargs)
            self.routes.append(
                {
                    "path": path,
                    "method": route["method"],
                    "func": route["func"],
                    "param_names": route["param_names"],
                    "param_converters": route["param_converters"],
                    "query_params": route["query_params"],
                    "expects_body": route["expects_body"],
                    "dependencies": route["dependencies"],
                    "expects_request": route.get("expects_request", False),
                    "background_param": route.get("background_param"),
                    "host": rhost,
                    "tags": route_tags,
                    "dependency_overrides": router.dependency_overrides,
                }
            )
        self._register_schema_route()
