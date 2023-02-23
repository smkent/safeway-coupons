FROM python:3-alpine
ARG POETRY_DYNAMIC_VERSIONING_BYPASS="0.0.0"
ENV CRON_SCHEDULE "5 2 * * *"
ENV SMTPHOST=
ENV SAFEWAY_ACCOUNT_USERNAME=
ENV SAFEWAY_ACCOUNT_PASSWORD=
ENV SAFEWAY_ACCOUNT_MAIL_FROM=
ENV SAFEWAY_ACCOUNT_MAIL_TO=
ENV SAFEWAY_ACCOUNTS_FILE=

RUN apk add --no-cache tini
COPY docker/entrypoint /

COPY . /python-build
RUN python3 -m pip install /python-build && rm -rf /python-build

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["/entrypoint"]
