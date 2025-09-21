"""Tests for GraphQL subscription handling over WebSockets."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

# Skip if the optional GraphQL dependency is not installed
pytest.importorskip("graphql", reason="graphql-core not installed")
from graphql import GraphQLField, GraphQLInt, GraphQLObjectType, GraphQLSchema

from forzium.app import ForziumApp
from forzium.websockets import WebSocket


async def counter(*_: object) -> Any:
    for i in range(3):
        yield i


schema = GraphQLSchema(
    query=GraphQLObjectType(
        name="Query",
        fields={"dummy": GraphQLField(GraphQLInt, resolve=lambda *_: 1)},
    ),
    subscription=GraphQLObjectType(
        name="Subscription",
        fields={
            "count": GraphQLField(
                GraphQLInt, subscribe=counter, resolve=lambda v, *_: v
            )
        },
    ),
)


def test_graphql_subscription_sends_events() -> None:
    app = ForziumApp()
    app.graphql_subscriptions("/graphql", schema)

    route = app.ws_routes[0]
    handler = app._make_ws_handler(
        route["func"], route["param_names"], route["param_converters"]
    )
    ws = WebSocket()
    ws.received.append('{"query":"subscription { count }"}')
    asyncio.run(handler(ws, ()))
    assert ws.sent == [
        '{"data":{"count":0}}',
        '{"data":{"count":1}}',
        '{"data":{"count":2}}',
    ]