---
title: Development workflow
icon: lucide/braces
---

# Project development workflow

## Cloning the repository

```sh
git clone https://github.com/smkent/safeway-coupons
cd safeway-coupons
```

Run `mise install` in new repository clones to install tools, dependencies, and
git hooks:

```sh
mise install
```

## Development tools

* `mise run lint`: Run formatters and static checks
* `mise run test`: Run tests

The `lint` and `test` tasks can also be run as a single combined command with:

```sh
mise run lt
```

### Test snapshots

Some tests compare test results with saved snapshots. Test snapshots can be
updated by running:

```sh
mise run snapup
```

## Documentation server

Start the development server with:

```sh
mise run docs
```

The documentation site will be served at:

[**http://localhost:8000**](http://localhost:8000){ .md-button .md-button--primary target="_blank" }

To use a different bind host/port, run `mise run docs --help` for usage info.
