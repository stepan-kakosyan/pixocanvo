# Pixel War (Docker)

## Project overview

Pixel War is a collaborative real-time pixel canvas web app where users place
pixels on a shared board, interact through chat, and participate in community-
based spaces. It is built as a Django application with WebSocket updates and a
Kafka pipeline for scalable pixel event processing.

## Project parts (short)

- `pixelwar` app: board logic, pixel updates, WebSocket consumer, chat, and
	app-specific views/templates/static assets
- `users` app: user accounts, profile data, forms, auth-related views, and
	signals
- `config`: Django project configuration (`settings`, URLs, ASGI/WSGI, routing)
- `locale`: multi-language translation files
- `media/avatars`: uploaded user avatar files
- `static` and `templates`: frontend assets and HTML templates
- `docker-compose.yml` and `Dockerfile`: containerized local/deployment setup

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

## Technologies used

- Python 3
- Django
- Django Channels (ASGI/WebSockets)
- Daphne
- Redis
- Apache Kafka
- MySQL (external)
- Docker and Docker Compose
- HTML, CSS, and JavaScript (frontend templates/static)

## Stop the stack

```bash
docker compose down
```

## Note

MySQL is not started by Docker Compose in this setup. Ensure your external
MySQL host is reachable from containers and credentials in `.env` are valid.
