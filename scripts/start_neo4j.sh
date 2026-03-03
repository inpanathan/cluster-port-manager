#!/bin/bash
# Start/stop Neo4j graph database in Docker.
#
# Usage:
#   bash scripts/start_neo4j.sh          # start (idempotent)
#   bash scripts/start_neo4j.sh stop     # stop and remove container
#   bash scripts/start_neo4j.sh status   # show container status
#
# Persistent storage: data/neo4j_data/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

CONTAINER_NAME="knowledge-hub-neo4j"
NEO4J_HTTP_PORT="${NEO4J_HTTP_PORT:-7474}"
NEO4J_BOLT_PORT="${NEO4J_BOLT_PORT:-7687}"
NEO4J_PASSWORD="${NEO4J__PASSWORD:-neo4j_dev}"
DATA_DIR="$PROJECT_ROOT/data/neo4j_data"

case "${1:-start}" in
    stop)
        echo "Stopping Neo4j..."
        docker stop "$CONTAINER_NAME" 2>/dev/null && docker rm "$CONTAINER_NAME" 2>/dev/null \
            && echo "Stopped and removed $CONTAINER_NAME" \
            || echo "Container $CONTAINER_NAME not running"
        exit 0
        ;;
    status)
        docker ps -a --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        exit 0
        ;;
    start)
        ;;
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac

# Stop existing container if running (REQ-RUN-005)
if docker ps -q --filter "name=$CONTAINER_NAME" 2>/dev/null | grep -q .; then
    echo "Stopping existing Neo4j container..."
    docker stop "$CONTAINER_NAME" >/dev/null
    docker rm "$CONTAINER_NAME" >/dev/null
fi

# Clean up stopped container with the same name
docker rm "$CONTAINER_NAME" 2>/dev/null || true

# Create data directory
mkdir -p "$DATA_DIR"

echo "Starting Neo4j..."
echo "  HTTP Port: $NEO4J_HTTP_PORT"
echo "  Bolt Port: $NEO4J_BOLT_PORT"
echo "  Data:      $DATA_DIR"
echo ""

docker run -d \
    --name "$CONTAINER_NAME" \
    -p "${NEO4J_HTTP_PORT}:7474" \
    -p "${NEO4J_BOLT_PORT}:7687" \
    -v "$DATA_DIR:/data:z" \
    -e NEO4J_AUTH="neo4j/${NEO4J_PASSWORD}" \
    -e NEO4J_PLUGINS='["apoc"]' \
    neo4j:5-community

# Wait for Neo4j to be ready
echo ""
echo "Waiting for Neo4j to start..."
for i in $(seq 1 30); do
    if curl -s "http://localhost:${NEO4J_HTTP_PORT}" >/dev/null 2>&1; then
        echo "Neo4j is running!"
        echo "  Browser:  http://localhost:${NEO4J_HTTP_PORT}"
        echo "  Bolt:     bolt://localhost:${NEO4J_BOLT_PORT}"
        echo "  Password: ${NEO4J_PASSWORD}"
        exit 0
    fi
    sleep 1
done

echo "WARNING: Neo4j may not be fully ready yet. Check: docker logs $CONTAINER_NAME"
