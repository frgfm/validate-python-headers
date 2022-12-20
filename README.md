# Header validator for your Python files

<p align="center">
  <a href="https://github.com/frgfm/validate-python-headers/actions?query=workflow%3Abuilds">
    <img alt="CI Status" src="https://img.shields.io/github/workflow/status/frgfm/validate-python-headers/builds?label=CI&logo=github&style=flat-square">
  </a>
  <a href="https://github.com/ambv/black">
    <img src="https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square" alt="black">
  </a>
  <a href="https://www.codacy.com/gh/frgfm/validate-python-headers/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=frgfm/validate-python-headers&amp;utm_campaign=Badge_Grade"><img src="https://app.codacy.com/project/badge/Grade/4e50e872d9fd4a378b696bdc0aea9301"/></a>
<p align="center">
  <img alt="GitHub release (latest by date)" src="https://img.shields.io/github/v/release/frgfm/validate-python-headers">
  <img alt="GitHub" src="https://img.shields.io/github/license/frgfm/validate-python-headers">
</p>


This action checks the copyright and license notices in the headers of your Python files.

## Inputs

### `license`

**Required** Identifier of the license for your project (cf. [SPDX identifiers](https://spdx.org/licenses/)).

### `owner`

**Required** The copyright owner.

### `starting-year`

**Required** The starting year of your project.

### `folders`

The folders to inspect, separated by a comma. Default `"."`.

### `ignore-files`

The files to ignore, separated by a comma. Default `"__init__.py"`.

### `ignore-folders`

The folders to ignore, separated by a comma. Default `".github/"`.

## Outputs

The list of files with header issues.

## Example usage

```
uses: frgfm/validate-python-headers@main
with:
  license: 'Apache-2.0'
  owner: 'François-Guillaume Fernandez'
  starting-year: 2022
  ignores: 'version.py,__init__.py'
```


## Contributing

Any sort of contribution is greatly appreciated!

You can find a short guide in [`CONTRIBUTING`](CONTRIBUTING) to help grow this project!



## License

Distributed under the Apache 2.0 License. See [`LICENSE`](LICENSE) for more information.
