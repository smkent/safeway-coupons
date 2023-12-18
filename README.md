# Automatic Safeway coupon clipper

[![PyPI](https://img.shields.io/pypi/v/safeway-coupons)][pypi]
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/safeway-coupons)][pypi]
[![Build](https://img.shields.io/github/checks-status/smkent/safeway-coupons/main?label=build)][gh-actions]
[![codecov](https://codecov.io/gh/smkent/safeway-coupons/branch/main/graph/badge.svg)][codecov]
[![GitHub stars](https://img.shields.io/github/stars/smkent/safeway-coupons?style=social)][repo]

**safeway-coupons** is a script that will log in to an account on safeway.com,
and attempt to select all of the "Safeway for U" electronic coupons on the site
so they don't have to each be clicked manually.

## Design notes

Safeway's sign in page is protected by a web application firewall (WAF).
safeway-coupons performs authentication using a headless instance of Google
Chrome. Authentication may fail based on your IP's reputation, either by
presenting a CAPTCHA or denying sign in attempts altogether. safeway-coupons
currently does not have support for prompting the user to solve CAPTCHAs.

Once a signed in session is established, coupon clipping is performed using HTTP
requests via [requests][requests].

## Installation and usage with Docker

A Docker container is provided which runs safeway-coupons with cron. The cron
schedule and your Safeway account details may be configured using environment
variables, or with an accounts file.

Example `docker-compose.yaml` with configuration via environment variables:

```yaml
version: "3.7"

services:
  safeway-coupons:
    image: ghcr.io/smkent/safeway-coupons:latest
    environment:
      CRON_SCHEDULE: "0 2 * * *"  # Run at 2:00 AM UTC each day
      # TZ: Antarctica/McMurdo  # Optional time zone to use instead of UTC
      SMTPHOST: your.smtp.host
      SAFEWAY_ACCOUNT_USERNAME: your.safeway.account.email@example.com
      SAFEWAY_ACCOUNT_PASSWORD: very_secret
      SAFEWAY_ACCOUNT_MAIL_FROM: your.email@example.com
      SAFEWAY_ACCOUNT_MAIL_TO: your.email@example.com
      # EXTRA_ARGS: --debug  # Optional
    restart: unless-stopped
```

Example `docker-compose.yaml` with configuration via accounts file:

```yaml
version: "3.7"

services:
  safeway-coupons:
    image: ghcr.io/smkent/safeway-coupons:latest
    environment:
      CRON_SCHEDULE: "0 2 * * *"  # Run at 2:00 AM UTC each day
      # TZ: Antarctica/McMurdo  # Optional time zone to use instead of UTC
      SMTPHOST: your.smtp.host
      SAFEWAY_ACCOUNTS_FILE: /accounts_file
      # EXTRA_ARGS: --debug  # Optional
    restart: unless-stopped
    volumes:
      - path/to/safeway_accounts_file:/accounts_file:ro
```

Start the container by running:

```console
docker-compose up -d
```

Debugging information can be viewed in the container log:

```console
docker-compose logs -f
```

## Installation from PyPI

### Prerequisites

* Google Chrome (for authentication performed via Selenium).
* Optional: `sendmail` (for email support)

### Installation

[safeway-coupons is available on PyPI][pypi]:

```console
pip install safeway-coupons
```

### Usage

For best results, run this program once a day or so with a cron daemon.

For full usage options, run

```console
safeway-coupons --help
```

### Configuration

**safeway-coupons** can clip coupons for one or more Safeway accounts in a
single run, depending on the configuration method used.

If a sender email address is configured, a summary email will be sent for each
Safeway account via `sendmail`. The email recipient defaults to the Safeway
account email address, but can be overridden for each account.

Accounts are searched via the following methods in the listed order. Only one
account configuration method may be used at a time.

#### With environment variables

A single Safeway account can be configured with environment variables:

* `SAFEWAY_ACCOUNT_USERNAME`: Account email address (required)
* `SAFEWAY_ACCOUNT_PASSWORD`: Account password (required)
* `SAFEWAY_ACCOUNT_MAIL_FROM`: Sender address for email summary
* `SAFEWAY_ACCOUNT_MAIL_TO`: Recipient address for email summary

#### With config file

Multiple Safeway accounts can be provided in an ini-style config file, with a
section for each account. For example:

```ini
email_sender = sender@example.com   ; optional

[safeway.account@example.com]       ; required
password = 12345                    ; required
notify = your.email@example.com     ; optional
```

Provide the path to your config file using the `-c` or `--accounts-config`
option:

```console
safeway-coupons -c path/to/config/file
```

## Development

### [Poetry][poetry] installation

Via [`pipx`][pipx]:

```console
pip install pipx
pipx install poetry
pipx inject poetry poetry-dynamic-versioning poetry-pre-commit-plugin
```

Via `pip`:

```console
pip install poetry
poetry self add poetry-dynamic-versioning poetry-pre-commit-plugin
```

### Invocation with docker-compose

safeway-coupons can be executed within a Docker container using
`docker-compose.dev.yaml`.

To use, first create an `accounts` file in the same directory with your
safeway-coupons accounts configuration. Then, execute safeway-coupons within a
container using docker-compose:

```console
docker-compose -f docker-compose.dev.yaml up --build
```

The container will run safeway-coupons once, attempt to clip one coupon, and
then stop.

To change the safeway-coupons arguments, modify the `command` value in
`docker-compose.dev.yaml`.

When finished with development tasks, the docker-compose state can be cleaned up
with:

```console
docker-compose -f docker-compose.dev.yaml down
```

### Development tasks

* Setup: `poetry install`
* Run static checks: `poetry run poe lint` or
  `poetry run pre-commit run --all-files`
* Run static checks and tests: `poetry run poe test`

---

Created from [smkent/cookie-python][cookie-python] using
[cookiecutter][cookiecutter]

[codecov]: https://codecov.io/gh/smkent/safeway-coupons
[cookie-python]: https://github.com/smkent/cookie-python
[cookiecutter]: https://github.com/cookiecutter/cookiecutter
[gh-actions]: https://github.com/smkent/safeway-coupons/actions?query=branch%3Amain
[pipx]: https://pypa.github.io/pipx/
[poetry]: https://python-poetry.org/docs/#installation
[pypi]: https://pypi.org/project/safeway-coupons/
[repo]: https://github.com/smkent/safeway-coupons
[requests]: https://requests.readthedocs.io/en/latest/
