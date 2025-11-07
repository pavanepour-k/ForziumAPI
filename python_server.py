#!/usr/bin/env python3
"""
A simple Python fallback server for ForziumAPI.
This is used when the Rust extension is not available.
"""

import sys
import json
import threading
from typing import Dict, Any, List
from http.server import HTTPServer, BaseHTTPRequestHandler
import socket
import json

class ComputeRequestSchema:
    """Schema for validating compute requests."""

    def __init__(self) -> None:
        self.required_keys = ("data", "operation")

    def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a compute request payload."""
        missing = [key for key in self.required_keys if key not in payload]
        if missing:
            raise ValueError(
                f"Missing keys for compute request validation: {missing}"
            )
        
        data = payload.get("data")
        if not isinstance(data, list) or not data:
            raise ValueError("Data must be a non-empty rectangular matrix")
        
        if not isinstance(data[0], list):
            raise ValueError("Data must be a matrix (list of lists)")
            
        row_len = len(data[0])
        for row in data:
            if not isinstance(row, list) or len(row) != row_len:
                raise ValueError("Data must be a non-empty rectangular matrix")
        
        result = dict(payload)
        if "parameters" not in result:
            result["parameters"] = {}
        return result


class ComputeEngine:
    """Compute engine with Python implementation."""

    def compute(
        self,
        data: List[List[float]],
        operation: str,
        parameters: Dict[str, Any],
    ) -> List[List[float]]:
        """Execute a computation operation."""
        # Python implementations
        if operation == "multiply":
            factor = float(parameters.get("factor", 1.0))
            return [[x * factor for x in row] for row in data]
        elif operation == "add":
            addend = float(parameters.get("addend", 0.0))
            return [[x + addend for x in row] for row in data]
        elif operation == "matmul":
            other = parameters.get("matrix_b")
            if not isinstance(other, list):
                raise ValueError("matrix_b parameter required")
            return self._matmul_python(data, other)
        else:
            raise ValueError(f"Unsupported operation: {operation}")

    def _matmul_python(self, a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
        """Python implementation of matrix multiplication."""
        if not a or not b or len(a[0]) != len(b):
            raise ValueError("Incompatible matrices")
        
        rows_a, cols_a = len(a), len(a[0])
        rows_b, cols_b = len(b), len(b[0])
        
        result = [[0.0 for _ in range(cols_b)] for _ in range(rows_a)]
        
        for i in range(rows_a):
            for j in range(cols_b):
                for k in range(cols_a):
                    result[i][j] += a[i][k] * b[k][j]
        
        return result


class ForziumHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the ForziumAPI."""
    
    def _set_headers(self, status_code=200, content_type='application/json'):
        self.send_response(status_code)
        self.send_header('Content-type', content_type)
        self.end_headers()
        
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/':
            self._set_headers()
            self.wfile.write(json.dumps({
                "message": "Forzium API server (Python fallback mode)"
            }).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({
                "error": "Not found"
            }).encode())
            
    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/compute':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            try:
                data = json.loads(post_data)
                schema = ComputeRequestSchema()
                validated = schema.validate(data)
                
                engine = ComputeEngine()
                result = engine.compute(
                    validated["data"],
                    validated["operation"],
                    validated.get("parameters", {})
                )
                
                self._set_headers()
                self.wfile.write(json.dumps({
                    "result": result
                }).encode())
            except Exception as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({
                    "error": str(e)
                }).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({
                "error": "Not found"
            }).encode())


def run_server(host="0.0.0.0", port=8000):
    """Run the HTTP server."""
    server_address = (host, port)
    httpd = HTTPServer(server_address, ForziumHTTPHandler)
    print(f"Python fallback server running at http://{host}:{port}")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        print("Server stopped.")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        run_server(host=sys.argv[1], port=int(sys.argv[2]))
    else:
        run_server()
