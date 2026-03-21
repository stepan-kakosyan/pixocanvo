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
- `celery`: background worker for notifications and email delivery tasks
- `kafka`: Kafka broker
- `redis`: cooldown cache + Channels layer
- external MySQL server configured via `.env` (`MYSQL_*` variables)

## AWS S3 storage for images

The project can store uploaded images and collected static assets in an AWS S3
bucket through Django storage backends.

Set these variables in your `.env` before starting containers:

```env
USE_S3=1
AWS_STORAGE_BUCKET_NAME=your-bucket-name
AWS_S3_REGION_NAME=eu-central-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_MEDIA_LOCATION=
AWS_S3_FILE_OVERWRITE=0
AWS_QUERYSTRING_AUTH=0
```

Optional variables:

```env
AWS_S3_CUSTOM_DOMAIN=cdn.example.com
AWS_S3_ENDPOINT_URL=
AWS_SESSION_TOKEN=
```

Behavior:

- when `USE_S3=1`, `ImageField` uploads are written to S3 under
	`AWS_MEDIA_LOCATION` (or bucket root when empty)
- avatar uploads go to `profile-avatars/...` and community covers go to
	`community_covers/...`
- when `USE_S3=0`, the project keeps using local `media/` and `staticfiles/`

If your image URLs must be public, configure the S3 bucket policy or CloudFront
distribution accordingly. The Django config uses unsigned URLs by default.

## Automated startup behavior

When `web` container starts, it automatically runs:

1. `npm install`
2. `npm run build:css`
3. `python manage.py collectstatic --noinput`
4. Daphne server startup

Migrations are intentionally **manual** and are not executed by containers at
startup. Run them explicitly when needed:

```bash
python manage.py migrate
```

`redis` is configured with `restart: on-failure:3` (up to 3 restart attempts).

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
