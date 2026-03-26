#!/bin/bash

# Aurora OSI Backend Diagnostic Script
# Tests backend connectivity, routes, and configuration

set -e

echo "==================================================================="
echo "Aurora OSI Backend Diagnostics"
echo "==================================================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKEND_URL="${AURORA_API_URL:-http://localhost:8000}"
API_BASE="${BACKEND_URL}/api/v1"

# Test functions
test_endpoint() {
  local method=$1
  local endpoint=$2
  local description=$3
  
  echo -n "Testing: $description... "
  
  if [ "$method" = "GET" ]; then
    response=$(curl -s -w "\n%{http_code}" "$BACKEND_URL$endpoint" 2>/dev/null || echo "error\n000")
  else
    response=$(curl -s -w "\n%{http_code}" -X "$method" "$BACKEND_URL$endpoint" 2>/dev/null || echo "error\n000")
  fi
  
  http_code=$(echo "$response" | tail -n 1)
  body=$(echo "$response" | head -n -1)
  
  if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✓ OK (200)${NC}"
    echo "  Response: $(echo "$body" | jq -r '.status // .app // .' 2>/dev/null || echo "$body")"
  elif [ "$http_code" = "404" ]; then
    echo -e "${RED}✗ NOT FOUND (404)${NC}"
    echo "  Endpoint does not exist or route not mounted"
  elif [ "$http_code" = "405" ]; then
    echo -e "${YELLOW}⚠ METHOD NOT ALLOWED (405)${NC}"
    echo "  This endpoint exists but the HTTP method is not supported"
  elif [ "$http_code" = "000" ]; then
    echo -e "${RED}✗ CONNECTION REFUSED${NC}"
    echo "  Backend is not running or unreachable at $BACKEND_URL"
  else
    echo -e "${YELLOW}⚠ Status $http_code${NC}"
  fi
  echo ""
}

# =========================================================================
# 1. Check Docker containers
# =========================================================================

echo "=== 1. DOCKER CONTAINERS ==="
echo ""
echo "Checking if Aurora backend container is running..."
echo ""

if ! command -v docker &> /dev/null; then
  echo -e "${RED}✗ Docker not found${NC}"
else
  containers=$(docker ps --filter "name=aurora" --format "table {{.Names}}\t{{.Status}}" 2>/dev/null || echo "")
  
  if [ -z "$containers" ]; then
    echo -e "${YELLOW}⚠ No Aurora containers found${NC}"
    echo ""
    echo "To start the backend:"
    echo "  cd aurora_vnext"
    echo "  docker compose up --build"
  else
    echo -e "${GREEN}✓ Aurora containers running:${NC}"
    docker ps --filter "name=aurora" --format "table {{.Names}}\t{{.Status}}" 2>/dev/null
  fi
fi

echo ""
echo ""

# =========================================================================
# 2. Test network connectivity
# =========================================================================

echo "=== 2. NETWORK CONNECTIVITY ==="
echo ""
echo "Backend URL: $BACKEND_URL"
echo ""

# Test basic connectivity
echo -n "Pinging backend... "
if nc -z -w 2 localhost 8000 2>/dev/null; then
  echo -e "${GREEN}✓ Port 8000 is open${NC}"
else
  echo -e "${RED}✗ Port 8000 is closed${NC}"
  echo "  Backend is not running on localhost:8000"
fi

echo ""
echo ""

# =========================================================================
# 3. Test Health & Version endpoints
# =========================================================================

echo "=== 3. BUILT-IN ENDPOINTS (Always Available) ==="
echo ""

test_endpoint "GET" "/health" "Health check endpoint"
test_endpoint "GET" "/version" "Version registry endpoint"

echo ""

# =========================================================================
# 4. Check API route status
# =========================================================================

echo "=== 4. API ROUTES STATUS ==="
echo ""
echo "The following routes are COMMENTED OUT in app/main.py and will return 404:"
echo ""

test_endpoint "GET" "$API_BASE/auth/me" "Auth — Get current user"
test_endpoint "POST" "$API_BASE/auth/login" "Auth — Login"
test_endpoint "GET" "$API_BASE/scan/active" "Scans — List active scans"
test_endpoint "GET" "$API_BASE/history" "History — List scan history"
test_endpoint "GET" "$API_BASE/datasets/summary/test-scan-id" "Datasets — Get summary"
test_endpoint "GET" "$API_BASE/twin/test-scan-id" "Twin — Get metadata"
test_endpoint "GET" "$API_BASE/admin/users" "Admin — List users"

echo ""
echo ""

# =========================================================================
# 5. Check frontend configuration
# =========================================================================

echo "=== 5. FRONTEND CONFIGURATION ==="
echo ""

if [ -f ".env.local" ]; then
  echo "Found .env.local:"
  grep -i "VITE_AURORA_API_URL" .env.local || echo "  VITE_AURORA_API_URL not set (using default: http://localhost:8000/api/v1)"
else
  echo ".env.local not found (frontend using default: http://localhost:8000/api/v1)"
fi

if [ -f ".env.production" ]; then
  echo "Found .env.production:"
  grep -i "VITE_AURORA_API_URL" .env.production || echo "  VITE_AURORA_API_URL not set"
fi

echo ""
echo ""

# =========================================================================
# 6. Summary & Next Steps
# =========================================================================

echo "=== 6. SUMMARY & NEXT STEPS ==="
echo ""

if [ "$http_code" = "200" ]; then
  echo -e "${GREEN}✓ Backend is running and healthy${NC}"
  echo ""
  echo "Next steps:"
  echo "  1. Verify routers are mounted in app/main.py (currently commented out)"
  echo "  2. Complete Phase F–O to uncomment API routers"
  echo "  3. Test API endpoints once routes are implemented"
  echo "  4. Deploy to AWS using CloudFormation template"
else
  echo -e "${RED}✗ Backend is not responding${NC}"
  echo ""
  echo "To fix:"
  echo "  1. Start Aurora backend:"
  echo "     cd aurora_vnext"
  echo "     docker compose up --build"
  echo ""
  echo "  2. Wait for startup log:"
  echo "     'Application startup complete'"
  echo ""
  echo "  3. Then re-run this script"
fi

echo ""
echo "==================================================================="
echo "End of Diagnostics"
echo "==================================================================="