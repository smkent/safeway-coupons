# About

safeway-coupons is a script that will log in to an account on safeway.com, and
attempt to select all of the "Just for U" electronic coupons on the site so
they don't have to each be clicked manually.

For best results, run this program once a day or so with a cron daemon.

# Usage

**Prerequisites:** Python 3 and sendmail.

Create a configuration file with an email sender address and your Safeway account
login information. For example:

```
[_global]
email_sender = sender@example.com

[safeway.account@example.com]
password = 12345
notify = your.email@example.com
```

(`notify` is optional, if you want to be notified at a different email.)

Specify the path to this config file using `-c` or `--accounts-config`.
