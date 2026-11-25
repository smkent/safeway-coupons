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

Safeway's sign in page may also require verifying a new device with a
multi-factor authentication (MFA) verification code. To reduce how often this
happens, a persistent Google Chrome profile directory is created for each
account and reused for logins with the same account. Once a signed in session is
established, coupon clipping is performed using HTTP requests via
[requests][requests].

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

By default, safeway-coupons runs for each configured account. To only run for
one or more specific accounts, specify each account name with `-a`/`--account`:

```sh
safeway-coupons -a main-account-name -a other-account-name
```

### Accounts configuration

**safeway-coupons** can clip coupons for one or more Safeway accounts in a
single run.

Commands are provided for managing accounts. The most useful commands are
listed below. For a full list of account management commands, run:

```sh
safeway-coupons accounts --help
```

#### Accounts file location

Account configuration is stored within `accounts.toml` in the local config
directory. To see the `accounts.toml` path, run:

```sh
safeway-coupons accounts path
```

#### Adding a new account

An account is referred to by a name you choose (similar to a label). Account
names are converted to lower case and may not contain spaces or slashes.

To add a new account, run:

```sh
safeway-coupons accounts add [account-name] [sign-in-email]
```

If `account-name` or `sign-in-email` from the above example are omitted,
`accounts add` will prompt for them interactively.

`accounts add` will prompt for an optional email sender and/or email recipient
address, for use if email summaries are enabled. These may be left blank to use
the sign in email instead.

#### Listing configured accounts

To list all configured accounts, run:

```sh
safeway-coupons accounts list
```

#### Updating an account password

To update the saved password for a configured account, run:

```sh
safeway-coupons accounts set-password <account-name>
```

#### Removing an account

To remove a configured account, run:

```sh
safeway-coupons accounts remove <account-name>
```

An account's persistent data, such as its browser profile, is not deleted
automatically. The `accounts remove` command shows the location of this
directory when an account is deleted.

#### Example `accounts.toml`

Each account is named using a [TOML table][toml-table] name placed within the
top level `accounts` table, e.g. `[accounts.(name)]`. Account names are
converted to lower case and may not contain spaces or slashes.

An example `accounts.toml`:

```toml
[accounts.main]
username = "safeway.account@example.com"
password = "base64:<base64-encoded password>"

# Optional summary email settings for "main" account
notify.email.to = "your.email@example.com"
notify.email.from = "sender@example.com"

[accounts.second]
username = "another.safeway.account@example.com"
password = "base64:<base64-encoded password>"
notify.email.to = "other.email@example.com"  # Optional
```

#### Migration from legacy ini-style configuration file

safeway-coupons previously supported an ini-style accounts configuration file
used with the now deprecated `-c`/`--accounts-config` option.

To import accounts from a legacy ini-style accounts configuration file, run:

```sh
safeway-coupons accounts import path/to/legacy/accounts/file
```

#### Migration from legacy environment variable account configuration

safeway-coupons previously supported using environment variables to configure a
single account. If legacy account configuration environment variables are set,
a warning is logged and `accounts.toml` is ignored.

Legacy environment variable based account configuration may be removed in a
future release. To migrate:

* Unset environment variables beginning with `SAFEWAY_ACCOUNT_`
* Configure the account by running:

```sh
safeway-coupons accounts add [account-name] [sign-in-email]
```

### Multi-factor authentication (MFA) verification codes

Safeway's sign in page will ask for an MFA code when signing in from a new
device, and occasionally on other logins.

When run interactively, safeway-coupons can request Safeway's sign in page to
send an MFA code to the first listed destination for your account (e.g. email or
text). safeway-coupons will then prompt for the code in the terminal to complete
sign in. To sign in interactively with an MFA code, run:

```sh
safeway-coupons --login-only
```

Scheduled and noninteractive invocations of safeway-coupons cannot obtain or
enter MFA verification codes. If the sign in page asks for an MFA code,
safeway-coupons exits with an error message. When this happens, run
safeway-coupons interactively to refresh your sign in session.

### Data storage

Local data storage defaults to these locations:

* [User config directory (see `user_config_dir`)][platformdirs-docs] for user
  configuration such as accounts
* [User state directory (see `user_state_dir`)][platformdirs-docs] for
  persistent state such as browser profiles

To view local data storage locations, run:

```sh
safeway-coupons storage list
```

## Installation and usage with Docker Compose

A Docker container is provided which runs safeway-coupons with cron. The cron
schedule may be configured using environment variables.

Example `compose.yaml`:

```yaml
services:
  safeway-coupons:
    image: ghcr.io/smkent/safeway-coupons:latest
    environment:
      CRON_SCHEDULE: 0 2 * * *  # Run at 2:00 AM UTC each day
      # TZ: Antarctica/McMurdo  # Optional time zone to use instead of UTC
      # SMTPHOST: your.smtp.host  # Optional SMTP host for sending summary emails
      # EXTRA_ARGS: --verbose  # Optional
    restart: unless-stopped
    volumes:
      - ./config:/storage/config:rw
      - state:/storage/state:rw

volumes:
  state:
```

With this example, account configuration is stored at `./config/accounts.toml`.

### Accounts configuration

To run specific safeway-coupons commands within a Docker compose configured
container, run:

```
docker compose run --rm safeway-coupons [command-arguments]
```

Accounts configuration with Docker uses the same accounts management commands
described in the main Installation and usage /
[Accounts configuration](#accounts-configuration) section. Examples:

* `docker compose run --rm safeway-coupons accounts add`
* `docker compose run --rm safeway-coupons accounts list`
* `docker compose run --rm safeway-coupons accounts set-password <account-name>`
* `docker compose run --rm safeway-coupons accounts remove <account-name>`

After configuring accounts, run safeway-coupons once to sign in to each of the
accounts, and enter any multi-factor authentication (MFA) verification codes if
prompted:

* `docker compose run --rm safeway-coupons --login-only`

Note that running safeway-coupons in a Docker container with no command
arguments (such as simply `docker compose run --rm safeway-coupons`) will run
the cron service instead of running safeway-coupons interactively.

#### Migration from legacy ini-style configuration file

safeway-coupons previously supported an ini-style accounts configuration file
used in Docker with the `SAFEWAY_ACCOUNTS_FILE` environment variable.

To import accounts from a legacy ini-style accounts configuration file using
`SAFEWAY_ACCOUNTS_FILE`:

* Ensure the container mounts a volume at `/storage/config` similar to the
  `compose.yaml` example. (Keep the `SAFEWAY_ACCOUNTS_FILE` environment variable
  and volume mount until a later step.)
* Convert the saved accounts to the new format and location by running:

```sh
docker compose run --rm safeway-coupons accounts import
```

* Remove the `SAFEWAY_ACCOUNTS_FILE` environment variable and associated volume
  mount from your Docker compose configuration (`compose.yaml`)
* Restart the service:

```sh
docker compose up -d
```

#### Migration from legacy environment variable account configuration

safeway-coupons previously supported using environment variables to configure a
single account. If legacy account configuration environment variables are set,
a warning is logged and `accounts.toml` is ignored.

Legacy environment variable based account configuration may be removed in a
future release. To migrate:

* Ensure the container mounts a volume at `/storage/config` similar to the
  `compose.yaml` example.
* Remove environment variables beginning with `SAFEWAY_ACCOUNT_` from your
  Docker compose configuration (`compose.yaml`)
* Configure the account by running:

```sh
docker compose run --rm safeway-coupons accounts add [account-name] [sign-in-email]
```

* Restart the service:

```sh
docker compose up -d
```

### Container usage

Start the container by running:

```sh
docker compose up -d
```

Debugging information can be viewed in the container log:

```sh
docker compose logs -f
```

Stop the container by running:

```sh
docker compose down
```

## Development

### Building a container locally with `docker compose`

To build the safeway-coupons container locally when using `docker compose`,
replace the `image:` line in your `compose.yaml` with `build: .`:

```yaml
services:
  safeway-coupons:
    # image: ghcr.io/smkent/safeway-coupons:latest  # Removed
    build: .
# [...]
```

Then, when using `docker compose up -d`, include `--build`:

```sh
docker compose up --build -d
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
[toml-table]: https://toml.io/en/v1.1.0#table
[uv-tool]: https://docs.astral.sh/uv/guides/tools/
