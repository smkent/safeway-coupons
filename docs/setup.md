---
title: One time setup
icon: lucide/package-plus
---

# One time setup

These steps only need to be completed once after the project is first created.

## GitHub repository

[Settings → General][repo-settings]:

**Releases**

- [x] Enable release immutability

**Pull Requests**

- [x] Allow merge commits
- [x] Allow squash merging
- [ ] Allow rebase merging
- [x] Automatically delete head branches

[Settings → Branches][repo-settings-branches] → Add branch protection rule
for the Default branch (`main`):

- [x] Restrict deletions
- [x] Require a pull request before merging
- [x] Block force pushes

[Issues → Labels][repo-labels] → Add label:

- Name: **breaking**
- Description: **Breaking change**
- Color: **#b60205** (or click the top left red color in the input popup)

!!! tip "Pull requests labeled `breaking` appear first in release notes"

## Renovate

Ensure the [Renovate app][renovate] is installed on your account, then
enable it for `smkent/safeway-coupons`.

## PyPI publishing

This project uses [trusted publishing][pypi-trusted-publishing] so no API tokens
need to be stored as secrets.

1. On PyPI, add a (pending) trusted publisher in your
   [Trusted Publisher Management][pypi-publishing-settings] settings:
     - Publisher: GitHub Actions
     - Owner: `smkent`
     - Repository: `safeway-coupons`
     - Workflow: `release.yaml`
     - Environment: `pypi`
2. Create the `pypi` environment in the GitHub repository:
   [Settings → Environments][repo-settings-envs] → New environment → `pypi`
3. Publish a release by pushing a tag:
   ```sh
   git tag v0.1.0  # or your desired first version number
   git push --tags
   ```

## GitHub Pages

[Settings → Pages][repo-settings-pages] → Source → GitHub Actions

[pypi-publishing-settings]: https://pypi.org/manage/account/publishing/
[pypi-trusted-publishing]: https://docs.pypi.org/trusted-publishers/
[renovate]: https://github.com/apps/renovate
[repo-labels]: https://github.com/smkent/safeway-coupons/labels
[repo-settings]: https://github.com/smkent/safeway-coupons/settings
[repo-settings-branches]: https://github.com/smkent/safeway-coupons/settings/branches
[repo-settings-envs]: https://github.com/smkent/safeway-coupons/settings/environments
[repo-settings-pages]: https://github.com/smkent/safeway-coupons/settings/pages
