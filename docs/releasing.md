---
title: Releasing a new version
icon: lucide/rocket
---

# Releasing a new version

Release version numbers should follow [Semantic Versioning][semver].

To create a release, run `mise run release` with one of `patch`, `minor`, or
`major` corresponding to the version number component to update:

```sh
mise run release patch|minor|major
```

A new tag with the new release version number will be created automatically
using [bump-my-version][bump-my-version] (for example, `v1.2.3`).

Afterward, push the new release tag:

```sh
git push --tags
```

* A corresponding [GitHub release][github-releases]
  will be created automatically.

    [![GitHub Release][github-release-badge]][github-release-latest]

* A release package will be built and [uploaded to PyPI][pypi-project].

    [![PyPI][pypi-badge]][pypi-project]

* A container image will be built and published to
  the [GitHub Container Registry (GHCR)][ghcr-docs].

[bump-my-version]: https://callowayproject.github.io/bump-my-version/
[ghcr-project]: https://github.com/smkent/safeway-coupons/pkgs/container/safeway-coupons
[github-release-badge]: https://img.shields.io/github/v/release/smkent/safeway-coupons
[github-release-latest]: https://github.com/smkent/safeway-coupons/releases/latest
[github-releases]: https://github.com/smkent/safeway-coupons/releases
[pypi-badge]: https://img.shields.io/pypi/v/safeway-coupons
[pypi-project]: https://pypi.org/project/safeway-coupons/
[semver]: https://semver.org/
