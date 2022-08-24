# Automatic clipper for Safeway "Just for U" coupons

[![Build](https://img.shields.io/github/checks-status/smkent/safeway-coupons/main?label=build)][gh-actions]
[![codecov](https://codecov.io/gh/smkent/safeway-coupons/branch/main/graph/badge.svg)][codecov]
[![GitHub stars](https://img.shields.io/github/stars/smkent/safeway-coupons?style=social)][repo]

**safeway-coupons** is a script that will log in to an account on safeway.com,
and attempt to select all of the "Just for U" electronic coupons on the site so
they don't have to each be clicked manually.

For best results, run this program once a day or so with a cron daemon.

## Prerequisites

* [Poetry][poetry]: `pip install poetry`
* sendmail (optional)

## Usage

Create a configuration file with an email sender address and your Safeway account
login information. For example:

```
email_sender = sender@example.com

[safeway.account@example.com]
password = 12345
notify = your.email@example.com
```

`email_sender` is optional. If included, a summary email will be sent for each
specified Safeway account, either to the account email address or to the
address specified by `notify`, if present.

Specify the path to this config file using `-c` or `--accounts-config`.

Execute `safeway-coupons` with Poetry:

```sh
poetry run safeway-coupons -c path/to/accounts_config_file
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
