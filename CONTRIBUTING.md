# Contributing to validate-python-headers

Everything you need to know to contribute efficiently to the project!

Whatever the way you wish to contribute to the project, please respect the [code of conduct](CODE_OF_CONDUCT.md).



## Codebase structure

- [`./src`](https://github.com/frgfm/validate-python-headers/blob/main/src) - The actual script used for header verification
- [`action.yml`](https://github.com/frgfm/validate-python-headers/blob/main/tests) - The marketplace action configuration file
- [`Dockerfile`](https://github.com/frgfm/validate-python-headers/blob/main/Dockerfile) - The dockerfile of the action
- [`entrypoint.sh`](https://github.com/frgfm/validate-python-headers/blob/main/entrypoint.sh) - The bash script executed by the Docker container


## Continuous Integration

This project uses the following integrations to ensure proper codebase maintenance:

- [Github Worklow](https://help.github.com/en/actions/configuring-and-managing-workflows/configuring-a-workflow) - run jobs for package build and coverage
- [Codacy](https://www.codacy.com/) - analyzes commits for code quality

As a contributor, you will only have to ensure coverage of your code by adding appropriate unit testing of your code.



## Feedback

### Feature requests & bug report

Whether you encountered a problem, or you have a feature suggestion, your input has value and can be used by contributors to reference it in their developments. For this purpose, we advise you to use Github [issues](https://github.com/frgfm/validate-python-headers/issues).

First, check whether the topic wasn't already covered in an open / closed issue. If not, feel free to open a new one! When doing so, use issue templates whenever possible and provide enough information for other contributors to jump in.

### Questions

If you are wondering how to do something with this action, or a more general question, you should consider checking out Github [discussions](https://github.com/frgfm/validate-python-headers/discussions). See it as a Q&A forum, or the project-specific StackOverflow!



## Submitting a Pull Request

### Preparing your local branch

1 - Fork this [repository](https://github.com/frgfm/validate-python-headers) by clicking on the "Fork" button at the top right of the page. This will create a copy of the project under your GitHub account (cf. [Fork a repo](https://docs.github.com/en/get-started/quickstart/fork-a-repo)).

2 - [Clone your fork](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository) to your local disk and set the upstream to this repo
```shell
git clone git@github.com:<YOUR_GITHUB_ACCOUNT>/validate-python-headers.git
cd validate-python-headers
git remote add upstream https://github.com/frgfm/validate-python-headers.git
```

3 - You should not work on the `main` branch, so let's create a new one
```shell
git checkout -b a-short-description
```

4 - You only have to set your development environment now, using the following command:
```shell
make build
```

### Developing your feature

#### Commits

- **Code**: ensure to provide docstrings to your Python code. In doing so, please follow [Google-style](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html) so it can ease the process of documentation later.
- **Commit message**: please follow [Udacity guide](http://udacity.github.io/git-styleguide/)

#### Action sanity check

In order to run the same checks as the CI workflows, you can run tests locally:

```shell
make test
```

#### Code quality

To run all quality checks together

```shell
make quality
```

The previous command won't modify anything in your codebase. Some fixes (import ordering and code formatting) can be done automatically using the following command:

```shell
make style
```

### Submit your modifications

Push your last modifications to your remote branch
```shell
git push -u origin a-short-description
```

Then [open a Pull Request](https://docs.github.com/en/github/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request) from your fork's branch. Follow the instructions of the Pull Request template and then click on "Create a pull request".
