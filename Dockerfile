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
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg && \
    echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main' > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update -y && \
    apt-get install -y google-chrome-stable --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Install tini for signal processing
RUN apt-get update -y && \
    apt-get install -y tini && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry using the official installer
WORKDIR /app
ENV POETRY_HOME="/opt/poetry"
RUN curl -sSL https://install.python-poetry.org | python3 -  && \
    chmod -R 777 $POETRY_HOME

# Add Poetry to PATH
ENV PATH="$POETRY_HOME/bin:$PATH"

# Copy project files
COPY pyproject.toml poetry.lock ./

# Install project dependencies via Poetry
RUN poetry config virtualenvs.options.system-site-packages false && \
    poetry install --no-root --no-interaction --disable-pip-cache

FROM python:3

# Copy installed Python project from builder
COPY --from=builder /opt/poetry /opt/poetry
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

ENV PATH="/opt/poetry/bin:$PATH"

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/entrypoint"]