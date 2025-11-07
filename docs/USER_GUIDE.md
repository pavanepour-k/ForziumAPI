# ForziumAPI User Guide

## Table of Contents
1. [Getting Started](#getting-started)
2. [Basic Usage](#basic-usage)
3. [Advanced Features](#advanced-features)
4. [Configuration](#configuration)
5. [Examples](#examples)
6. [Troubleshooting](#troubleshooting)

## Getting Started

### Installation
```bash
pip install -r requirements.txt
```

### Running the Server
```bash
python run_server.py
```

The server will start on `http://localhost:8000` by default.

### Your First API
Create a simple API with just a few lines:

```python
from forzium import ForziumApp

app = ForziumApp()

@app.get("/")
def hello():
    return {"message": "Hello, ForziumAPI!"}

@app.get("/health")
def health():
    return {"status": "healthy"}
```

## Basic Usage

### Health Check
```bash
curl http://localhost:8000/health
```

### Simple Data Processing
```bash
curl -X POST http://localhost:8000/compute \
  -H "Content-Type: application/json" \
  -d '{
    "data": [[1, 2], [3, 4]],
    "operation": "multiply",
    "parameters": {"factor": 2}
  }'
```

### Response Format
All responses follow a consistent JSON format:
```json
{
  "status": "success",
  "data": { ... },
  "message": "Operation completed"
}
```

## Advanced Features

### Async Handlers
ForziumAPI supports async/await for better performance:

```python
import asyncio

@app.post("/async-compute")
async def async_compute(payload: dict):
    # Simulate async work
    await asyncio.sleep(0.1)
    return {"result": "processed", "data": payload}
```

### Streaming Responses
Handle large datasets efficiently:

```python
from forzium import StreamingResponse

@app.get("/stream")
def stream_data():
    def generate():
        for i in range(1000):
            yield f"data: {i}\n\n"
    
    return StreamingResponse(generate(), media_type="text/plain")
```

### Request Validation
Automatic validation with helpful error messages:

```python
from pydantic import BaseModel

class ComputeRequest(BaseModel):
    data: list[list[float]]
    operation: str
    parameters: dict

@app.post("/validate")
def validate_request(request: ComputeRequest):
    return {"received": request.dict()}
```

### Background Tasks
Execute tasks after sending the response:

```python
from forzium import BackgroundTasks

def log_operation(data: dict):
    print(f"Operation completed: {data}")

@app.post("/background")
def background_task(data: dict, background_tasks: BackgroundTasks):
    background_tasks.add_task(log_operation, data)
    return {"status": "processing"}
```

## Configuration

### Environment Variables
Configure your server using environment variables:

```bash
# Server settings
export HOST=0.0.0.0
export PORT=8000
export FORZIUM_DEBUG=1

# Rate limiting
export FORZIUM_RATE_LIMIT=100
export FORZIUM_RATE_LIMIT_WINDOW=60

# Performance
export FORZIUM_MAX_UPLOAD_SIZE=10485760  # 10MB
```

### Configuration Options
| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server host address |
| `PORT` | `8000` | Server port |
| `FORZIUM_DEBUG` | `0` | Enable debug mode |
| `FORZIUM_RATE_LIMIT` | `1000` | Requests per window |
| `FORZIUM_RATE_LIMIT_WINDOW` | `60` | Rate limit window (seconds) |
| `FORZIUM_MAX_UPLOAD_SIZE` | `10485760` | Max upload size (bytes) |

## Examples

### Complete API Example
```python
from forzium import ForziumApp, BackgroundTasks
from pydantic import BaseModel
from typing import List

app = ForziumApp()

class User(BaseModel):
    name: str
    email: str
    age: int

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

# In-memory storage (use a database in production)
users = []
next_id = 1

@app.get("/users")
def get_users() -> List[UserResponse]:
    return [UserResponse(id=u["id"], name=u["name"], email=u["email"]) 
            for u in users]

@app.post("/users")
def create_user(user: User, background_tasks: BackgroundTasks) -> UserResponse:
    global next_id
    
    new_user = {
        "id": next_id,
        "name": user.name,
        "email": user.email,
        "age": user.age
    }
    users.append(new_user)
    next_id += 1
    
    # Log the creation in background
    background_tasks.add_task(print, f"Created user: {user.name}")
    
    return UserResponse(id=new_user["id"], name=new_user["name"], email=new_user["email"])

@app.get("/users/{user_id}")
def get_user(user_id: int) -> UserResponse:
    for user in users:
        if user["id"] == user_id:
            return UserResponse(id=user["id"], name=user["name"], email=user["email"])
    return {"error": "User not found"}
```

### Error Handling
```python
from forzium import HTTPException

@app.get("/users/{user_id}")
def get_user(user_id: int):
    for user in users:
        if user["id"] == user_id:
            return user
    raise HTTPException(status_code=404, detail="User not found")
```

## Troubleshooting

### Python Fallback Mode

ForziumAPI includes an automatic fallback to a pure Python implementation when the Rust extension is not available. This ensures your service can run even if the Rust components haven't been built.

**How it works:**
- When `python run_server.py` is executed, the system first tries to use the Rust server
- If the Rust extension isn't available, it automatically falls back to the Python implementation
- The Python fallback provides the same API endpoints with identical request/response formats
- All core functionality works, but with lower performance than the Rust version

**Building the Rust extension:**
To switch from fallback mode to high-performance mode:
```bash
python build.py
```

This will compile the Rust extension and enable all performance optimizations.

**Identifying the mode:**
You can check which mode you're running in by the startup messages:
- Rust mode: "ForziumAPI server running at http://..." 
- Python mode: "Python fallback server running at http://..."

### Common Issues

**Server won't start:**
- Check if port 8000 is available
- Verify all dependencies are installed
- Check for syntax errors in your code

**Slow responses:**
- Enable debug mode to see request timing
- Check if you're using async handlers for I/O operations
- Monitor memory usage for large datasets
- Verify you're running with the Rust extension (not in fallback mode)

**Validation errors:**
- Check your request format matches the expected schema
- Verify Content-Type headers are set correctly
- Review error messages for specific field issues

### Getting Help
1. Check the [Release Notes](release_notes.md) for known issues
2. Review the [Developer Documentation](developer/README.md) for technical details
3. Enable debug mode for detailed logging

### Performance Tips
- Use async handlers for I/O operations
- Implement streaming for large responses
- Set appropriate rate limits
- Monitor memory usage with large datasets
