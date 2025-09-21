"""Tests for GraphQL federation support."""

import pytest

# Skip the entire module if the optional GraphQL dependency is missing
pytest.importorskip("graphql", reason="graphql-core not installed")
from graphql import GraphQLField, GraphQLObjectType, GraphQLSchema, GraphQLString

from forzium.app import ForziumApp
from forzium.testclient import TestClient


def test_federated_schema_combines_fields() -> None:
    schema_a = GraphQLSchema(
        query=GraphQLObjectType(
            name="QA",
            fields={"hello": GraphQLField(GraphQLString, resolve=lambda *_: "world")},
        )
    )
    schema_b = GraphQLSchema(
        query=GraphQLObjectType(
            name="QB",
            fields={"greet": GraphQLField(GraphQLString, resolve=lambda *_: "hi")},
        )
    )

    app = ForziumApp()
    app.graphql_federation("/graphql", [schema_a, schema_b])

    client = TestClient(app)
    response = client.post("/graphql", json_body={"query": "{ hello greet }"})
    assert response.status_code == 200
    assert response.json() == {"data": {"hello": "world", "greet": "hi"}}