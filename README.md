# Automatic Safeway coupon clipper

[![Build](https://img.shields.io/github/checks-status/smkent/safeway-coupons/main?label=build)][gh-actions]
[![codecov](https://codecov.io/gh/smkent/safeway-coupons/branch/main/graph/badge.svg)][codecov]
[![GitHub stars](https://img.shields.io/github/stars/smkent/safeway-coupons?style=social)][repo]

**safeway-coupons** is a script that will log in to an account on safeway.com,
and attempt to select all of the "Safeway for U" electronic coupons on the site
so they don't have to each be clicked manually.

For best results, run this program once a day or so with a cron daemon.

## Prerequisites

* [Poetry][poetry]: `pip install poetry`
* sendmail (optional)

## Usage

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
option.

### Invocation

First, install the project dependencies with [Poetry][poetry]:
```sh
poetry install
```

Execute `safeway-coupons` with Poetry:

```sh
poetry run safeway-coupons
```

## Development

* Setup: `poetry install`
* Run all tests: `poetry run poe test`
* Fix linting errors: `poetry run poe lint`

---

Created from [smkent/cookie-python][cookie-python] using
[cookiecutter][cookiecutter]

[codecov]: https://codecov.io/gh/smkent/safeway-coupons
[cookie-python]: https://github.com/smkent/cookie-python
[cookiecutter]: https://github.com/cookiecutter/cookiecutter
[gh-actions]: https://github.com/smkent/safeway-coupons/actions?query=branch%3Amain
[poetry]: https://python-poetry.org/docs/#installation
[repo]: https://github.com/smkent/safeway-coupons
