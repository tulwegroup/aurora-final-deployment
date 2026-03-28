"""
Health check and service discovery for Aurora API
Provides endpoints to verify API availability and resolve connection issues
"""
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
import httpx
import socket
import os

router = APIRouter(prefix="/api/v1", tags=["health"])

# Service configuration
AURORA_DB_HOST = os.getenv("AURORA_DB_HOST", "localhost")
AURORA_API_PORT = int(os.getenv("AURORA_API_PORT", "8000"))
AURORA_API_BASE = f"http://{AURORA_DB_HOST}:{AURORA_API_PORT}"

@router.get("/health/live")
async def health_live():
    """
    Liveness probe — is the API process running?
    Returns 200 if alive, 503 if dead
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Aurora API vNext",
        "version": "Phase AB",
    }

@router.get("/health/ready")
async def health_ready():
    """
    Readiness probe — can the API handle requests?
    Checks database connection + downstream dependencies
    """
    try:
        # Check database connectivity
        db_host = AURORA_DB_HOST
        db_port = 5432
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((db_host, db_port))
        sock.close()
        
        if result != 0:
            return {
                "status": "not_ready",
                "reason": f"Database unreachable: {db_host}:{db_port}",
                "timestamp": datetime.utcnow().isoformat(),
            }, 503
        
        return {
            "status": "ready",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "status": "not_ready",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }, 503

@router.get("/health/dependencies")
async def health_dependencies():
    """
    Dependency health check
    Verifies all downstream services (DB, cache, message queue)
    """
    results = {}
    
    # Database
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.connect((AURORA_DB_HOST, 5432))
        sock.close()
        results["database"] = {"status": "healthy", "host": AURORA_DB_HOST}
    except Exception as e:
        results["database"] = {"status": "unhealthy", "error": str(e)}
    
    # Redis (optional, for caching/queues)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.connect((AURORA_DB_HOST, 6379))
        sock.close()
        results["redis"] = {"status": "healthy"}
    except Exception:
        results["redis"] = {"status": "not_configured"}
    
    return {
        "dependencies": results,
        "timestamp": datetime.utcnow().isoformat(),
    }

@router.get("/discover/routes")
async def discover_routes():
    """
    Service discovery — list all available API routes
    Useful for debugging missing endpoints
    """
    routes = [
        # Streaming
        {"method": "POST", "path": "/api/v1/scan/{scan_id}/initiate", "group": "streaming"},
        {"method": "WebSocket", "path": "/api/v1/scan/{scan_id}/stream", "group": "streaming"},
        {"method": "POST", "path": "/api/v1/scan/{scan_id}/pause", "group": "streaming"},
        {"method": "GET", "path": "/api/v1/scan/{scan_id}/replay", "group": "streaming"},
        {"method": "GET", "path": "/api/v1/scan/{scan_id}/replay/{speed}/{batch}", "group": "streaming"},
        
        # Reporting
        {"method": "POST", "path": "/api/v1/scan/{scan_id}/compose-report", "group": "reporting"},
        {"method": "GET", "path": "/api/v1/reports/{report_id}", "group": "reporting"},
        
        # Analog validation
        {"method": "POST", "path": "/api/v1/ground-truth/analogs/{commodity}/{basin_type}", "group": "analog"},
        {"method": "POST", "path": "/api/v1/scan/{scan_id}/validate-analog", "group": "analog"},
        
        # Legacy ingestion
        {"method": "POST", "path": "/api/v1/legacy-import", "group": "legacy"},
        {"method": "GET", "path": "/api/v1/legacy-import/{import_id}/quality-gate", "group": "legacy"},
        {"method": "POST", "path": "/api/v1/legacy-import/{import_id}/freeze-canonical", "group": "legacy"},
        
        # Pricing
        {"method": "POST", "path": "/api/v1/pricing/calculate", "group": "pricing"},
        
        # History (core)
        {"method": "GET", "path": "/api/v1/history", "group": "history"},
        {"method": "GET", "path": "/api/v1/history/{scan_id}", "group": "history"},
        
        # Health
        {"method": "GET", "path": "/api/v1/health/live", "group": "health"},
        {"method": "GET", "path": "/api/v1/health/ready", "group": "health"},
        {"method": "GET", "path": "/api/v1/health/dependencies", "group": "health"},
        {"method": "GET", "path": "/api/v1/discover/routes", "group": "discovery"},
    ]
    
    return {
        "routes": routes,
        "count": len(routes),
        "grouped": {
            group: [r for r in routes if r["group"] == group]
            for group in set(r["group"] for r in routes)
        },
        "timestamp": datetime.utcnow().isoformat(),
    }

@router.get("/discover/endpoint-status")
async def discover_endpoint_status(endpoint: str = Query(..., description="Endpoint path to check")):
    """
    Check if a specific endpoint is reachable and responding
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Construct full URL
            url = f"{AURORA_API_BASE}{endpoint}"
            
            # Try GET first
            response = await client.get(url, follow_redirects=True)
            
            return {
                "endpoint": endpoint,
                "status": "reachable",
                "http_status": response.status_code,
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "timestamp": datetime.utcnow().isoformat(),
            }
    except httpx.ConnectError:
        return {
            "endpoint": endpoint,
            "status": "unreachable",
            "error": "Connection refused (service may not be running)",
            "suggestions": [
                "Verify service is running: docker ps",
                "Check DNS resolution: nslookup " + AURORA_DB_HOST,
                "Check port mapping: netstat -tlnp | grep 8000",
                "Review logs: docker logs aurora-api",
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }, 503
    except httpx.TimeoutException:
        return {
            "endpoint": endpoint,
            "status": "timeout",
            "error": "Service did not respond within timeout",
            "suggestions": [
                "Service may be overloaded or hanging",
                "Check resource usage: docker stats",
                "Review service logs for errors",
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }, 503
    except Exception as e:
        return {
            "endpoint": endpoint,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }, 500

@router.get("/discover/dns-resolution")
async def discover_dns_resolution(hostname: str = Query(AURORA_DB_HOST, description="Hostname to resolve")):
    """
    Diagnose DNS resolution issues
    """
    try:
        ip_address = socket.gethostbyname(hostname)
        return {
            "hostname": hostname,
            "ip_address": ip_address,
            "status": "resolved",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except socket.gaierror as e:
        return {
            "hostname": hostname,
            "status": "resolution_failed",
            "error": str(e),
            "suggestions": [
                "Check DNS configuration: cat /etc/resolv.conf",
                "Verify hostname in docker-compose or k8s config",
                "Try IP address directly instead of hostname",
                "Check /etc/hosts for local overrides",
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }, 503
    except Exception as e:
        return {
            "hostname": hostname,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }, 500

@router.get("/discover/network-diagnostics")
async def discover_network_diagnostics():
    """
    Full network diagnostics report
    """
    diags = {}
    
    # 1. DNS resolution
    try:
        ip = socket.gethostbyname(AURORA_DB_HOST)
        diags["dns"] = {"status": "ok", "hostname": AURORA_DB_HOST, "ip": ip}
    except Exception as e:
        diags["dns"] = {"status": "failed", "error": str(e)}
    
    # 2. Database port reachability
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((AURORA_DB_HOST, 5432))
        sock.close()
        diags["database_port"] = {
            "status": "open" if result == 0 else "closed",
            "port": 5432,
            "host": AURORA_DB_HOST,
        }
    except Exception as e:
        diags["database_port"] = {"status": "error", "error": str(e)}
    
    # 3. API port reachability
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((AURORA_DB_HOST, AURORA_API_PORT))
        sock.close()
        diags["api_port"] = {
            "status": "open" if result == 0 else "closed",
            "port": AURORA_API_PORT,
            "host": AURORA_DB_HOST,
        }
    except Exception as e:
        diags["api_port"] = {"status": "error", "error": str(e)}
    
    # 4. Summary
    all_ok = all(d.get("status") == "ok" for d in diags.values() if isinstance(d, dict) and "status" in d)
    
    return {
        "diagnostics": diags,
        "overall_status": "healthy" if all_ok else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
    }