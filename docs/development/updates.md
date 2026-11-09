---
title: Template updates
icon: lucide/git-merge
---

# Applying copier-project template updates

Copier can update your project with template changes that have occurred since
the project was created.

To apply updates, simply run in your project directory:

```sh
copier update
```

This will repeat the setup prompts, in case any prompts have been added or
changed.

!!! tip
    To change template-provided features in your project, simply change your
    answers in the update prompts.

To apply updates without being prompted (reusing all previous answers), run:

```sh
copier update -l
```

When [`copier update`][copier-update] is finished, view changes with
`git status` and `git diff`. Resolve any conflicts, and then commit the result.

[copier-update]: https://copier.readthedocs.io/en/stable/updating/
