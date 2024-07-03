# Header validator for your Python files

<p align="center">
  <a href="https://github.com/frgfm/validate-python-headers/actions/workflows/builds.yml">
    <img alt="CI Status" src="https://img.shields.io/github/actions/workflow/status/frgfm/validate-python-headers/builds.yml?branch=main&label=CI&logo=github&style=flat-square">
  </a>
  <a href="https://github.com/astral-sh/ruff">
    <img src="https://img.shields.io/badge/Linter-Ruff-FCC21B?style=flat-square&logo=ruff&logoColor=white" alt="ruff">
  </a>
  <a href="https://github.com/astral-sh/ruff">
    <img src="https://img.shields.io/badge/Formatter-Ruff-FCC21B?style=flat-square&logo=Python&logoColor=white" alt="ruff">
  </a>
  <a href="https://www.codacy.com/gh/frgfm/validate-python-headers/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=frgfm/validate-python-headers&amp;utm_campaign=Badge_Grade"><img src="https://app.codacy.com/project/badge/Grade/4e50e872d9fd4a378b696bdc0aea9301"/></a>
<p align="center">
  <img alt="GitHub release (latest by date)" src="https://img.shields.io/github/v/release/frgfm/validate-python-headers">
  <img alt="GitHub" src="https://img.shields.io/github/license/frgfm/validate-python-headers">
</p>


This action checks the copyright and license notices in the headers of your Python files.

## Inputs

### `owner`

**Required** The copyright owner.

### `starting-year`

**Required** The starting year of your project.

### `license`

Identifier of the license for your project (cf. [SPDX identifiers](https://spdx.org/licenses/)). Default `null`.

### `folders`

The folders to inspect, separated by a comma. Default `"."`.

### `ignore-files`

The files to ignore, separated by a comma. Default `"__init__.py"`.

### `ignore-folders`

The folders to ignore, separated by a comma. Default `".github/"`.

### `license-notice`

The path to a license notice text. If license is `null`, the header will be expected to have this text as a license notice. Default `null`.

## Outputs

The list of files with header issues.

## Example usages

Using an Open-source license:

```
uses: frgfm/validate-python-headers@main
with:
  license: 'Apache-2.0'
  owner: 'François-Guillaume Fernandez'
  starting-year: 2022
  ignore-files: 'version.py,__init__.py'
  ignore-folders: '.github/'
```

On closed source code:

```
uses: frgfm/validate-python-headers@main
with:
  license-notice: '.github/license-notice.txt'
  owner: 'François-Guillaume Fernandez'
  starting-year: 2022
  ignore-files: 'version.py,__init__.py'
  ignore-folders: '.github/'
```


## Contributing

Any sort of contribution is greatly appreciated!

You can find a short guide in [`CONTRIBUTING`](CONTRIBUTING.md) to help grow this project!



## License

Distributed under the Apache 2.0 License. See [`LICENSE`](LICENSE) for more information.
