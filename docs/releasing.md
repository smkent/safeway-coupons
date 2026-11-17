---
title: Releasing a new version
icon: lucide/rocket
---

# Releasing a new version

Release version numbers should follow [Semantic Versioning][semver].

Project releases are created automatically when a correctly formatted
[git tag][git-book-tags] is created within the GitHub repository.

## Preparing release notes

Release notes are generated using the titles of pull requests merged since the
previous release. Items in release notes are grouped in the following order
based on how the corresponding pull request is labeled:

| Pull request label | Release notes section |
|---|---|
| `breaking` | 💥 Breaking changes |
| `enhancement` | ✨ New features |
| `bug` | 🐛 Fixes |
| `documentation` | 📝 Documentation |
| `dependencies` | 📦 Dependencies |
| All other items | 💾 General changes |

Before publishing a release, review and adjust the labels on pull requests
merged since the previous release to ensure items will appear in the desired
release notes sections.

!!! tip

    Pull requests with multiple matching labels appear in release notes within
    the first matching section.

### Previewing release notes with the GitHub CLI

If the [GitHub CLI][github-cli] `gh` is available, you can preview the release
notes that will be generated with:

```sh
mise run release-notes
```

The previewed release notes will show `(preview)` in place of a new release
version.

## Publishing a release

To create a release, run `mise run release -n` with one of `patch`, `minor`, or
`major` corresponding to the version number component to update.

```sh
mise run release -n patch|minor|major
```

This will display:

* A preview of the release notes, if the [GitHub CLI][github-cli] `gh` is
  available
* The new version number that would be created and pushed automatically using
  [bump-my-version][bump-my-version] (for example, `v1.2.3`).

!!! info

    Always run `mise run release` with `-n` or `--dry-run` first to preview new
    release details!

After confirming everything looks right, run the same command again without `-n`
to create and push the release tag:

```sh
mise run release patch|minor|major
```

When a release tag is created in the GitHub repository:

* A release package is built.
* The release package is [uploaded to PyPI][pypi-project].

    [![PyPI][pypi-badge]][pypi-project]

* A corresponding [GitHub release][github-releases] is created.

    [![GitHub Release][github-release-badge]][github-release-latest]

* A container image is built and published to the
  [GitHub Container Registry (GHCR)][ghcr-docs].

[bump-my-version]: https://callowayproject.github.io/bump-my-version/
[ghcr-docs]: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
[git-book-tags]: https://git-scm.com/book/en/v2/Git-Basics-Tagging
[github-cli]: https://cli.github.com/
[github-release-badge]: https://img.shields.io/github/v/release/smkent/safeway-coupons
[github-release-latest]: https://github.com/smkent/safeway-coupons/releases/latest
[github-releases]: https://github.com/smkent/safeway-coupons/releases
[pypi-badge]: https://img.shields.io/pypi/v/safeway-coupons
[pypi-project]: https://pypi.org/project/safeway-coupons/
[semver]: https://semver.org/
