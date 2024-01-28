FROM busybox

FROM python:3
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

RUN DEBIAN_FRONTEND=noninteractive && \
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub > /usr/share/keyrings/chrome.pub && \
    echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/chrome.pub] http://dl.google.com/linux/chrome/deb/ stable main' > /etc/apt/sources.list.d/google-chrome.list && \
    apt update -y && \
    apt install -y google-chrome-stable
RUN apt install -y tini

# Install busybox utilities using static binary from official image
COPY --from=busybox /bin/busybox /bin/busybox
RUN for target in /usr/sbin/sendmail /usr/sbin/crond /usr/bin/crontab; do \
    ln -svf /bin/busybox ${target}; \
    done

COPY docker/entrypoint /

COPY . /python-build
RUN python3 -m pip install /python-build && rm -rf /python-build
RUN safeway-coupons-init-chromedriver

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/entrypoint"]
