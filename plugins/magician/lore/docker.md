Common AI mistakes: running as root; copying entire context with `COPY .` (use .dockerignore); not using multi-stage builds; storing secrets in ENV/ARG.
Commands: build: `docker build -t name .`, run: `docker run`, compose: `docker compose up`.
Gotchas: each RUN creates a layer — chain commands with &&; use non-root USER; HEALTHCHECK for production images; multi-stage builds reduce final image size.
