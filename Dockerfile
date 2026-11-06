FROM python:3 as builder

ARG POETRY_DYNAMIC_VERSIONING_BYPASS="0.0.0"
ENV CRON_SCHEDULE "5 2 * * *"
ENV SMTPHOST=
ENV SAFEWAY_ACCOUNT_USERNAME=
ENV SAFEWAY_ACCOUNT_PASSWORD=
ENV SAFEWAY_ACCOUNT_MAIL_FROM=
ENV SAFEWAY_ACCOUNT_MAIL_TO=
ENV SAFEWAY_ACCOUNTS_FILE=
ENV DEBUG_DIR="/debug"
ENV EXTRA_ARGS=

# Install system deps including Chrome in one layer with proper cleanup
RUN DEBIAN_FRONTEND=noninteractive && \
    apt-get update -y && \
    apt-get install -y wget gnupg && \
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo 'deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main' > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update -y && \
    apt-get install -y google-chrome-stable --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Install tini for signal processing
RUN apt-get update -y && \
    apt-get install -y tini && \
    rm -rf /var/lib/apt/lists/*

# Install Python project via Poetry
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
    poetry config virtualenv.create-system-site-packages true && \
    poetry install --no-root --no-interaction --disable-pip-cache

FROM python:3

# Copy installed Python project from builder
COPY --from=builder /usr/local/lib/python3.*/site-packages /usr/local/lib/python3./site-packages
COPY --from=builder /app /app

# Copy entrypoint and set up
COPY docker/entrypoint /
RUN chmod +x /entrypoint

# Install tini for proper process management
RUN apt-get update -y && \
    apt-get install -y tini && \
    rm -rf /var/lib/apt/lists/*

# Create busybox symlinks for sendmail/crond if needed
RUN for target in /usr/sbin/sendmail /usr/sbin/crond /usr/bin/crontab; do \
    if [ ! -f ${target} ]; then ln -sf /bin/busybox ${target}; fi; \
    done

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/entrypoint"]