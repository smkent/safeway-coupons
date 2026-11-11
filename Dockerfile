FROM python:3.15-slim AS builder

COPY --from=ghcr.io/astral-sh/uv /uv /uvx /bin/

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-default-groups --no-install-project

# Install project
COPY README.md COPYING .
COPY safeway_coupons/ ./safeway_coupons/
ARG UV_DYNAMIC_VERSIONING_BYPASS=0.0.0
RUN uv sync --locked --no-default-groups --no-editable

FROM python:3.15-slim

LABEL org.opencontainers.image.licenses="GPL-3.0-or-later"

ENV CRON_SCHEDULE="5 2 * * *"
ENV SMTPHOST=
ENV SAFEWAY_ACCOUNT_USERNAME=
ENV SAFEWAY_ACCOUNT_PASSWORD=
ENV SAFEWAY_ACCOUNT_MAIL_FROM=
ENV SAFEWAY_ACCOUNT_MAIL_TO=
ENV SAFEWAY_ACCOUNTS_FILE=
ENV DEBUG_DIR="/debug"
ENV EXTRA_ARGS=

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates wget && \
    wget -q -O /usr/share/keyrings/chrome.pub https://dl-ssl.google.com/linux/linux_signing_key.pub && \
    echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/chrome.pub] http://dl.google.com/linux/chrome/deb/ stable main' \
        > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y google-chrome-stable tini && \
    rm -rf /var/lib/apt/lists/*

# Install busybox utilities using static binary from official image
COPY --from=busybox /bin/busybox /bin/busybox
RUN for target in /usr/sbin/sendmail /usr/sbin/crond /usr/bin/crontab; do \
    ln -svf /bin/busybox ${target}; \
    done

COPY --from=builder /app/.venv /app/.venv

COPY docker/entrypoint /

VOLUME /state

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/usr/bin/tini", "-s", "--"]
CMD ["/entrypoint"]
