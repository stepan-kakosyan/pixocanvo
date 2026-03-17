# Pixo Canvo (Docker)

## Start the stack

```bash
docker compose up --build
```

The web app will be available at http://localhost:8000.

## Services

- `web`: Django + Daphne (HTTP + WebSocket)
- `consumer`: Kafka consumer that bulk-upserts pixels and broadcasts updates
- `kafka`: Kafka broker
- `zookeeper`: Kafka dependency
- `redis`: cooldown cache + Channels layer
- external MySQL server configured via `.env` (`MYSQL_*` variables)

## Stop the stack

```bash
docker compose down
```

## Note

MySQL is not started by Docker Compose in this setup. Ensure your external
MySQL host is reachable from containers and credentials in `.env` are valid.
