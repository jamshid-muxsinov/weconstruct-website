import hashlib
import json
import time
from typing import Callable
from fastapi import Request, Response
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse

from src.pages.jinja_config import templates
from src.core.cache import cache_manager
from src.core.config import get_settings

settings = get_settings()

class HTMXMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, templates: Jinja2Templates):
        super().__init__(app)
        self.templates = templates

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        is_htmx = request.headers.get("HX-Request") == "true"
        request.state.htmx_request = is_htmx
        self.templates.env.globals['htmx_request'] = is_htmx
        response = await call_next(request)
        return response

class CacheMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, cache_ttl: int = 300):
        super().__init__(app)
        self.cache_ttl = cache_ttl
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method != "GET":
            return await call_next(request)
        
        if request.url.path.startswith(("/admin", "/api", "/docs", "/openapi")):
            return await call_next(request)
        
        cache_key = self._generate_cache_key(request)
        
        cached_response = await cache_manager.get(cache_key)
        if cached_response:
            return Response(
                content=cached_response["content"],
                status_code=cached_response["status_code"],
                headers=cached_response["headers"],
                media_type=cached_response["media_type"]
            )
        
        response = await call_next(request)
        
        if (response.status_code == 200 and 
            "text/html" in response.headers.get("content-type", "") and
            not isinstance(response, StreamingResponse)):
            
            content = b""
            async for chunk in response.body_iterator:
                content += chunk
            
            cached_response = Response(
                content=content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
            
            cache_data = {
                "content": content,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type
            }
            await cache_manager.set(cache_key, cache_data, self.cache_ttl)
            
            return cached_response
        
        return response
    
    def _generate_cache_key(self, request: Request) -> str:
        """Генерация ключа кэша для HTTP ответа"""
        key_parts = [
            "http_response",
            request.url.path,
            str(request.query_params),
            request.headers.get("accept-language", ""),
            request.headers.get("user-agent", "")[:100]  
        ]
        
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware для ограничения скорости запросов"""
    
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_counts = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        
        current_time = int(time.time())
        window_key = f"rate_limit_{client_ip}_{current_time // self.window_seconds}"
        
        current_count = await cache_manager.get(window_key) or 0
        
        if current_count >= self.max_requests:
            return Response(
                content="Too many requests",
                status_code=429,
                media_type="text/plain"
            )
        
        await cache_manager.set(window_key, current_count + 1, self.window_seconds)
        
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(self.max_requests - current_count - 1)
        response.headers["X-RateLimit-Reset"] = str((current_time // self.window_seconds + 1) * self.window_seconds)
        
        return response
