# safeway-coupons

Automatic coupon clipper for Safeway's online "Safeway for U" coupons

[![License](https://img.shields.io/github/license/smkent/safeway-coupons)](https://github.com/smkent/safeway-coupons/blob/main/COPYING)
[![PyPI](https://img.shields.io/pypi/v/safeway-coupons)](https://pypi.org/project/safeway-coupons/)
[![Python](https://img.shields.io/pypi/pyversions/safeway-coupons)](https://pypi.org/project/safeway-coupons/)
[![CI](https://github.com/smkent/safeway-coupons/actions/workflows/ci.yaml/badge.svg)](https://github.com/smkent/safeway-coupons/actions/workflows/ci.yaml)
[![Coverage](https://codecov.io/gh/smkent/safeway-coupons/branch/main/graph/badge.svg)](https://codecov.io/gh/smkent/safeway-coupons)
[![Renovate](https://img.shields.io/badge/renovate-enabled-brightgreen?logo=renovatebot)](https://renovatebot.com)
[![GitHub stars](https://img.shields.io/github/stars/smkent/safeway-coupons?style=social)](https://github.com/smkent/safeway-coupons)

**safeway-coupons** is a tool that will log in to an account on safeway.com,
and attempt to select all of the "Safeway for U" electronic coupons on the site
so they don't have to each be clicked manually.

## Design notes

Safeway's sign in page is protected by a web application firewall (WAF).
safeway-coupons performs authentication using Google Chrome. Authentication may
fail based on your IP's reputation, either by presenting an interactive
challenge or denying sign in attempts altogether.

safeway-coupons currently does not have support for prompting the user to solve
interactive challenges.

Safeway's sign in page may also require an email verification code. Support for
email verification codes is being evaluated. To reduce the frequency of MFA
challenges, a persistent Google Chrome profile directory is created for each
account and reused for logins with the same account. These are stored within the
[User state directory (see `user_state_dir`)][platformdirs-docs].

Once a signed in session is established, coupon clipping is performed using HTTP
requests via [requests][requests].

## Installation and usage

### Prerequisites

* [Google Chrome][google-chrome]
  (for authentication performed via [patchright][patchright]).
* Optional: `sendmail` (for email support)

### Installation

Installation with [`uv`][uv-tool] or [`pipx`][pipx] is recommended:

```sh
uv tool install safeway-coupons
```

```sh
pipx install safeway-coupons
```

Installation with `pip` is also available:

```sh
pip install safeway-coupons
```

### Usage

For best results, run this program once a day or so with a cron daemon.

For full usage options, run

```sh
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

```sh
safeway-coupons -c path/to/config/file
```

## Installation and usage with Docker Compose

A Docker container is provided which runs safeway-coupons with cron. The cron
schedule and your Safeway account details may be configured using environment
variables, or with an accounts file.

Example `compose.yaml` with configuration via environment variables:

```yaml
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
    volumes:
      - state:/state:rw

volumes:
  state:
```

Example `compose.yaml` with configuration via accounts file:

```yaml
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
      - state:/state:rw

volumes:
  state:
```

Start the container by running:

```sh
docker compose up -d
```

Debugging information can be viewed in the container log:

```sh
docker compose logs -f
```

## Development

### Invocation with `docker compose`

safeway-coupons can be executed within a Docker container using
`compose.dev.yaml`.

To use, first create an `accounts` file in the same directory with your
safeway-coupons accounts configuration. Then, execute safeway-coupons within a
container using `docker compose`:

```sh
docker compose -f compose.dev.yaml up --build
```

The container will run safeway-coupons once, attempt to clip one coupon, and
then stop.

To change the safeway-coupons arguments, modify the `command` value in
`compose.dev.yaml`.

When finished with development tasks, the `docker compose` state can be cleaned
up with:

```sh
docker compose -f compose.dev.yaml down
```

## License

Copyright (C) 2012 Stephen Kent and contributors

Licensed under the GNU General Public License v3.0 or later
([`GPL-3.0-or-later`](https://github.com/smkent/safeway-coupons/blob/main/COPYING)).

## Project template

This project is based on and maintained with [copier-project][copier-project].

[copier-project]: https://smkent.github.io/copier-project
[google-chrome]: https://www.google.com/chrome/
[patchright]: https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python
[pipx]: https://pipx.pypa.io
[platformdirs-docs]: https://platformdirs.readthedocs.io/en/stable/platforms.html
[requests]: https://requests.readthedocs.io/en/latest/
[uv-tool]: https://docs.astral.sh/uv/guides/tools/
