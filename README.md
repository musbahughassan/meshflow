# MeshFlow 💬

A real-time chat API built with Django, Django REST Framework, and Django Channels. Users can create chat rooms, add members, and exchange messages in real time over WebSockets, with full message history available over REST.

## Features

- **User authentication** — signup, login, logout via JWT
- **Chat rooms with membership** — create rooms, add members by username; only room members can read or participate
- **Real-time messaging** — WebSocket-based, authenticated, broadcast to all connected members of a room
- **Message history** — persisted to Postgres, retrievable over REST, read-only (messages are created only via WebSocket)

## Tech Stack

- Python / Django
- Django REST Framework (REST endpoints: auth, rooms, membership, message history)
- Django Channels + Daphne (ASGI server, WebSocket support)
- Redis (channel layer — pub/sub backing for real-time broadcast)
- PostgreSQL
- `djangorestframework-simplejwt` (JWT auth, also used for WebSocket authentication)

## Project Structure

```
meshflow/
├── core/           # Custom User model
├── chat/           # Room, Membership, Message models
│   ├── models.py
│   ├── serializers.py
│   ├── views.py         # REST: rooms, membership, message history
│   ├── permissions.py
│   ├── consumers.py      # WebSocket consumer — real-time messaging
│   ├── routing.py        # WebSocket URL routing
│   └── middleware.py     # JWT auth for WebSocket connections
├── meshflow/
│   ├── settings.py
│   ├── asgi.py           # ASGI application, routes HTTP + WebSocket
│   └── urls.py
└── manage.py
```

## Setup

### 1. Install dependencies

```bash
pipenv install
pipenv shell
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```
DB_NAME=meshflow_db
DB_USER=your_pg_user
DB_PASSWORD=your_pg_password
DB_HOST=localhost
DB_PORT=5432
SECRET_KEY=your-django-secret-key
```

### 3. Start Postgres and Redis (Docker)

```bash
docker run -d --name meshflow-postgres -p 5432:5432 -e POSTGRES_PASSWORD=yourpassword postgres:16
docker run -d --name meshflow-redis -p 6379:6379 redis:7
```

### 4. Run migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Start the server

WebSockets require an ASGI server — the regular `runserver` won't serve them:

```bash
daphne meshflow.asgi:application
```

## API Endpoints

All REST endpoints are prefixed with `/chat/` or `/auth/` (adjust to match your actual URL config).

### Auth

| Method | Endpoint | Description | Auth required |
|--------|----------|--------------|----------------|
| POST | `/auth/signup/` | Create a new user account | No |
| POST | `/auth/login/` | Log in, returns `access` + `refresh` tokens | No |
| POST | `/auth/login/refresh/` | Exchange refresh token for new access token | No |
| POST | `/auth/logout/` | Blacklist a refresh token | Yes |

### Rooms (`/chat/rooms/`)

| Method | Endpoint | Description | Auth required |
|--------|----------|--------------|----------------|
| GET | `/rooms/` | List rooms you're a member of | Yes |
| POST | `/rooms/` | Create a room (creator auto-joins) | Yes |
| GET | `/rooms/{id}/` | Retrieve a room | Yes (member) |
| POST | `/rooms/{id}/add_member/` | Add a user to the room by username | Yes (creator only) |
| GET | `/rooms/{id}/messages/` | Message history for the room | Yes (member) |

### WebSocket

```
ws://<host>/ws/chat/{room_id}/?token=<access_token>
```

- Authenticates the connection using the JWT access token passed as a query parameter
- Rejects the connection if the user isn't authenticated (`4001`) or isn't a member of the room (`4003`)
- **Send:** `{"content": "your message"}`
- **Receive:** broadcast to all connected members of the room:
  ```json
  {"id": 13, "sender": "username", "content": "your message", "created_at": "..."}
  ```

## Authentication Flow

MeshFlow uses JWT for both REST and WebSocket authentication:

1. **Signup / Login** — same as a standard JWT flow; login returns `access` and `refresh` tokens.
2. **REST requests** — send the access token in the `Authorization` header:
   ```
   Authorization: Bearer <access_token>
   ```
3. **WebSocket connections** — since WebSocket handshakes can't carry custom headers the way HTTP can, the access token is passed as a query parameter instead:
   ```
   ws://host/ws/chat/1/?token=<access_token>
   ```
   A custom middleware (`chat/middleware.py`) decodes this token and attaches the authenticated user to the connection scope before the consumer runs.

## Permissions

- Only authenticated users who are **members of a room** can read its messages or connect to its WebSocket.
- Only the **room creator** can add new members.
- Messages cannot be created via REST (`MessageViewSet` is read-only) — creation happens exclusively through the WebSocket consumer, keeping the real-time path and the history-retrieval path cleanly separated.

## Data Models

**User** (`core.User`) — extends Django's `AbstractUser`.

**Room** (`chat.Room`)
- `name`
- `created_by` (FK to User)
- `created_at`

**Membership** (`chat.Membership`)
- `room` (FK)
- `user` (FK)
- `joined_at`
- Unique together: `(room, user)` — a user can't join the same room twice

**Message** (`chat.Message`)
- `room` (FK)
- `sender` (FK to User)
- `content`
- `created_at`
- Ordered oldest-first (chronological, like a conversation)

## How Real-Time Messaging Works

1. Client opens a WebSocket connection to `/ws/chat/{room_id}/` with a valid access token.
2. The consumer verifies authentication and room membership, then joins a Redis-backed "group" named after the room (`chat_{room_id}`).
3. When a client sends a message, the consumer saves it to Postgres, then broadcasts it to every connection in that room's group via the Redis channel layer.
4. All connected members — including the sender — receive the message instantly, with no polling or refresh required.

This was verified with three simultaneous WebSocket connections (different users, same room), confirming messages broadcast correctly to all members and remain consistent with the REST message history afterward.

## Deployment

MeshFlow is deployed on **AWS Lightsail** (Ubuntu 22.04), containerized with Docker Compose.

### Stack on the server

- `docker-compose.yml` runs four services: `db` (Postgres), `redis`, `web` (Daphne/Django), `nginx`
- `nginx` is the only service exposed to the internet (port 80); it reverse-proxies both regular HTTP traffic and WebSocket connections to `web`
- `db` and `redis` are only reachable from other containers on the Docker network, never exposed externally

### Why Lightsail

Chosen over raw EC2 for simplicity: flat monthly pricing, a static public IP included by default, and a simpler firewall UI — while still being a real Linux box, so the same Docker Compose setup that runs locally runs identically on the server.

### Key deployment details

- **Static files and migrations run at container *startup*, not build time** (`entrypoint.sh`), since environment variables from `.env` are only available once the container is running — not during `docker build`.
- **nginx requires explicit WebSocket upgrade headers** (`proxy_set_header Upgrade $http_upgrade;` / `Connection "upgrade";`) on the `/ws/` location block — without these, nginx treats WebSocket connection attempts as plain HTTP and they fail.
- **Service names, not `localhost`, are used for inter-container communication** — e.g. `DB_HOST=db` and `redis://redis:6379/2` in `CHANNEL_LAYERS`, matching the service names in `docker-compose.yml`.
- **Verified in production** with a real multi-client test: two separate WebSocket connections (different users, different devices) exchanging messages live over the public IP, with message history matching between the WebSocket stream and the REST `/messages/` endpoint afterward.

### Redeploying after a code change

```bash
git pull
docker compose up -d --build
```

### Known deployment gaps

- Currently HTTP/WS only, not HTTPS/WSS — fine for testing, but browsers increasingly restrict mixed content, and production use should add a domain + TLS (e.g. via Certbot).
- Single-instance setup — Postgres, Redis, and the app all run on one Lightsail instance with no redundancy; an instance restart takes everything down together.
- `ALLOWED_HOSTS` is currently permissive (`*`) for ease of testing; should be locked to the actual domain/IP before any real public use.

## Known Limitations / Future Improvements

- No invite-link/token-based room joining — members are added directly by the creator via username.
- No typing indicators, read receipts, or online-presence tracking.
- No pagination on message history yet.
- No test suite yet.
- For production: swap Daphne's dev-friendly defaults for a proper ASGI deployment (e.g. Daphne or Uvicorn behind Nginx), and move Redis/Postgres to managed services.

## Author

Built by [your name] as a real-time systems project, extending the REST API patterns from an earlier project (Inkwell) with WebSocket-based real-time features via Django Channels.
