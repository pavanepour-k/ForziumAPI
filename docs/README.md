# ForziumAPI Documentation

Welcome to ForziumAPI! This is a high-performance web framework that combines the ease of FastAPI with the speed of Rust.

## What is ForziumAPI?

ForziumAPI is a FastAPI-compatible web framework that provides:
- **High Performance**: Rust-backed HTTP server with Python handlers
- **Easy to Use**: Familiar FastAPI syntax and patterns
- **Async Support**: Full async/await support for route handlers
- **Built-in Features**: Rate limiting, streaming responses, and observability

## Quick Start

### 1. Installation
```bash
pip install -r requirements.txt
```

### 2. Start the Server
```bash
python run_server.py
```

### 3. Test Your API
```bash
curl http://localhost:8000/health
```

## Documentation

### For Users
- **[User Guide](USER_GUIDE.md)** - Complete guide with examples and best practices
- **[Release Notes](release_notes.md)** - What's new and version history

### For Developers
- **[Developer Documentation](developer/README.md)** - Technical documentation for contributors
- **[Architecture](developer/architecture.md)** - System design and technical details
- **[Enterprise Guide](developer/enterprise_adoption_note.md)** - Enterprise deployment processes
- **[Performance Metrics](developer/performance_baseline.md)** - Performance benchmarks
- **[Testing Guidelines](developer/normalization_rules.md)** - QA and testing procedures

## Key Features

### FastAPI Compatibility
ForziumAPI maintains full compatibility with FastAPI patterns:

```python
from forzium import ForziumApp

app = ForziumApp()

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/compute")
async def compute(payload: dict) -> dict:
    result = await process_data(payload)
    return {"result": result}
```

### Built-in Capabilities
- **Validation**: Automatic request/response validation
- **Streaming**: Support for large data streams
- **Rate Limiting**: Built-in protection against abuse
- **Observability**: Request tracing and metrics
- **Background Tasks**: Async task execution

## Getting Help

1. **Start with the [User Guide](USER_GUIDE.md)** for detailed examples
2. **Check [Release Notes](release_notes.md)** for latest changes
3. **Review [Architecture](architecture.md)** for technical understanding

## Next Steps

Ready to build your first API? Head to the [User Guide](USER_GUIDE.md) to get started with examples and best practices.