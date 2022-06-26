# Header validator for your Python files

This action checks the copyright and license notices in the headers of your Python files.

## Inputs

## `license`

**Required** Identifier of the license for your project (cf. [SPDX identifiers](https://spdx.org/licenses/)).

## `owner`

**Required** The copyright owner.

## `starting-year`

**Required** The starting year of your project.

## `folders`

The folders to inspect, separated by a comma. Default `"."`.

## `ignores`

The files to ignore, separated by a comma. Default `""`.

## Outputs

## `time`

The time we greeted you.

## Example usage

uses: frgfm/validate-python-headers@main
with:
  license: 'Apache-2.0'
  owner: 'François-Guillaume Fernandez'
  starting-year: 2022
  ignores: 'version.py,__init__.py'
