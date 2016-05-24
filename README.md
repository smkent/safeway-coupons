# About

safeway-coupons is a script that will log in to an account on safeway.com, and
attempt to select all of the "Just for U" electronic coupons on the site so
they don't have to each be clicked manually.

For best results, run this program once a day or so with a cron daemon.

# Usage

**Prerequisites:** Python 3 and sendmail (optional).

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
