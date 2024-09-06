# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased] - yyyy-mm-dd

## [2.0.0] - 2024-09-06

>**IMPORTANT**<br>This release requires Alliance Auth 4+ and will no longer work with older versions of Alliance Auth.

### Changed

- Adopted the AA4 templates.

## [1.19.1] - 2024-08-29

### Changed

- Exclude `/path-to/setuptools/_vendored` import paths from dump command by default

## [1.19.0] - 2024-08-29

### Added

- Dump command can now also resolve the paths of all distribution files
- Dump command now also shows useful meta information incl. the total count of duplicates

### Changed

- Dump command now defaults to the YAML format

## [1.18.0] - 2024-08-29

### Added

- Command to dump the list of all installed Python packages. Call with `python manage.py packagemonitorcli dump`.

### Changed

- Consolidated management command `package-monitor-refresh` into `packagemonitorcli refresh`.

## [1.17.3] - 2024-07-23

### Fixed

- Some distributions packages (e.g. `jaraco.text`) reported with the wrong current version

## [1.17.2] - 2024-07-22

### Fixed

- KeyError when trying to show name of a corrupt distribution package

## [1.17.1] - 2024-07-22

### Fixed

- Update process breaks with "KeyError" exception when encountering invalid distributions.

## [1.17.0] - 2024-07-13

### Added

- Recurring time for update notifications can now be specified precisely and in natural language:
  - In the last release we introduced a new feature that allows receiving update notifications less often, e.g. only once a day or once a week. This release replaces the "timeout" implementation of that feature with a "schedule" implementation. The schedule implementation allows the user to define a concrete schedule for update notifications in natural language, e.g. "every day at 12 o'clock".
  - To try out this new feature we recommend the following settings. This will produce a daily notification about any pending updates at 18:00:
    - `PACKAGE_MONITOR_NOTIFICATIONS_SCHEDULE = "every day at 18:00"`
    - `PACKAGE_MONITOR_NOTIFICATIONS_REPEAT = True`
  - For more details please see the documentation for the new settings: `PACKAGE_MONITOR_NOTIFICATIONS_SCHEDULE`.

### Changed

- The timeout setting introduced in the last release has been removed.

## [1.16.0] - 2024-06-18

### Added

- You can now set a timeout for update notifications, so that update notifications will be sent less often, e.g. only once every 24 hours. This is disabled by default to keep the existing behavior. For more info see the new setting: `PACKAGE_MONITOR_NOTIFICATIONS_TIMEOUT` in the README.

- You can now choose to get repeated notifications about the same updates. This is useful in combination with the new timeout feature and works like a repeating reminder. This feature is disabled by default to keep the existing behavior. For more info see the new setting: `PACKAGE_MONITOR_NOTIFICATIONS_REPEAT` in the README. This is off by default.

### Changed

- Combine messages when multiple package update are available (#14)

## [1.15.1] - 2024-03-22

### Fixed

- TypeError: 'NoneType' object is not iterable (#15)

## [1.15.0] - 2024-03-20

### Added

- Some updates to installed packages might also trigger updates of other packages, which could potentially break the current AA installation. For example: if you have aa-esi-status v1.x installed with Alliance Auth v3 and update to aa-esi-status v2.x, it will automatically also update to Alliance Auth to v4, which would then requires additional manual installation steps or AA will no longer function.

To address this, such potentially unwanted updates can now be automatically excluded for specific packages. See also setting `PACKAGE_MONITOR_PROTECTED_PACKAGES` for details.

### Changed

- Available updates to installed packages, which would also cause an update to Django or Alliance Auth, will no longer be shown. See also setting `PACKAGE_MONITOR_PROTECTED_PACKAGES` for details.

## [1.14.0] - 2023-11-27

### Added

- Add support for AA 4

## [1.13.0] - 2023-10-08

### Added

- German localization (:de:)

## [1.12.0] - 2023-07-25

### Added

- Ability to specify additional local requirements via settings. This allows you to block package monitor from showing upgrades to versions that you are not interested in (e.g. because a specific version is broken or you want to keep an older version for compatibility reasons.)

## [1.11.1] - 2023-07-15

### Changed

- Use asyncio instead of threads for fetching data from PyPI
- Reenable feature for Python markers (requires packaging>22)
- Add pylint to CI

### Fixed

- Update task duration is too long (#3)

## [1.11.0] - 2023-07-14

### Added

- Added support for Python 3.11

### Changed

- Demoted log messages about ignoring invalid versions to info
- Migrated to flit for build
- Refactored core logic
- Improved test suite

## [1.10.0] - 2023-05-09

### Added

- Russian translations

## [1.9.2] - 2023-05-02

### Fixed

- Fails to identify Django app when module has no file

## [1.9.1] - 2023-04-26

### Changed

- Improve performance when checking for installed Django apps in distribution package

### Fixed

- Various minor fixes

## [1.9.0] - 2023-04-22

### Changed

- Added localization to enable translations

### Changed

- Now shows link to PyPI project page instead of the project's homepage
- Build process migrated to PEP 621
- Added support for AA 4 / Django 4
- Dropped support for AA 3 / Django 3.1

### Fixed

- PEP 660 packages are not detected as editable
- Does not show homepage for some packages (#6)

## [1.8.1] - 2023-01-04

### Fixed

- Fetching info from PyPI for a package breaks when requires_python contains an invalid specifer

## [1.8.0] - 2023-01-03

### Changed

- Removed support for Python 3.7
- Added support fro Python 3.10

### Fixed

- Fetching info from PyPI for a package breaks when history contains releases with invalid versions

## [1.7.0] - 2022-09-15

### Added

- Ability to notify admins when an update is available for a currently installed distribution package (#7)

## [1.6.2] - 2022-09-12

### Changed

- Additional technical improvements & changes

## [1.6.1] - 2022-09-11

### Changed

- Technical improvements
- Better tests

## [1.6.0] - 2022-08-30

### Added

- Ability to exclude distribution packages via new setting
- Ability to exclude editable packages via new setting

### Changed

- No longer shows editable packages by default

## [1.5.0] - 2022-08-02

### Update notes

This version is changing the default to showing all packages. So if you have been using the default you might suddenly see a lot of missing updates after installing this patch. Our main rationale for changing this is that during the update to AA3 we have seen many users running outdated packages, which have caused problems.

### Changed

- Changing the default to showing all packages.
- Unused `filterDropDown.js` removed from template (!6)

## [1.4.2] - 2022-06-18

### Changed

- Migrated to clipboard-js library (Thank you @ppfeufer for the contribution)
- Add wheel to PyPI deployment

## [1.4.1] - 2022-06-05

### Changed

- Reverted copy-to-clipboard logic back execCommand approach. While this approach is officially deprecated, it works in more scenarios (e.g. does not requires HTTPS).

### Fixed

- `KeyError: 'latest'`

## [1.4.0] - 2022-06-04

### Added

- It is now possible to get the pip install command for installing all outdated packages together.

### Changed

- Install command is now shown in the tooltip

## [1.3.0] - 2022-03-01

### Changed

- Dropped support for Python 3.6
- Dropped support for Django 3.1

## [1.2.2] - 2021-12-09

### Fixed

- Modal for refreshing distributions now shows an error when the server is not reachable

## [1.2.1] - 2021-10-30

### Changed

- Added tests for AA 2.9 / Django 3.2 to CI
- Remove packaging as dependency (!2)

## [1.2.0] - 2021-07-20

### Changed

- Removed support for Django 2
- Add isort to CI
- Integrated allianceauth-app-utils

### Fixed

- Fix "Column 'website_url' cannot be null" (#5)

## [1.1.0] - 2020-11-11

### Added

- Shows the effective requirements of packages under "Used By" as tool tip [#1](https://gitlab.com/ErikKalkoken/aa-package-monitor/-/issues/1)

### Fixed

- KeyError: 'latest': [#2](https://gitlab.com/ErikKalkoken/aa-package-monitor/-/issues/2)

## [1.0.1] - 2020-11-05

### Fixed

- Spinner optimizes for light/dark mode
- Does no longer show vertical slider on full page
- Does no longer try to process distribution packages that have no name
- Fix white spaces and EOF in all files

## [1.0.0] - 2020-10-24

### Changed

- Will now show "update available" tab as default if there are updates
- Improved styling
- Improved text matrix

## [1.0.0b2] - 2020-09-22

### Changed

- Removed dependency conflict with Auth and Django 3

### Fixed

- Did not always recognize packages with capitals correctly (e.g. "Django").

## [1.0.0b1] - 2020-09-16

### Important Note for alpha users

Users of the alpha release will need to "migrate zero" their old installation before installing the beta version, because the migrations have been recreated from scratch for the beta.

### Added

- Initial beta release
