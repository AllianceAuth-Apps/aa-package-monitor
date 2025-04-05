# Package Monitor

An app for keeping track of installed packages and outstanding updates with Alliance Auth.

[![release](https://img.shields.io/pypi/v/aa-package-monitor?label=release)](https://pypi.org/project/aa-package-monitor/)
[![python](https://img.shields.io/pypi/pyversions/aa-package-monitor)](https://pypi.org/project/aa-package-monitor/)
[![django](https://img.shields.io/pypi/djversions/aa-package-monitor?label=django)](https://pypi.org/project/aa-package-monitor/)
[![pipeline](https://gitlab.com/ErikKalkoken/aa-package-monitor/badges/master/pipeline.svg)](https://gitlab.com/ErikKalkoken/aa-package-monitor/-/pipelines)
[![codecov](https://codecov.io/gl/ErikKalkoken/aa-package-monitor/branch/master/graph/badge.svg?token=IIV0I6UGBH)](https://codecov.io/gl/ErikKalkoken/aa-package-monitor)
[![license](https://img.shields.io/badge/license-MIT-green)](https://gitlab.com/ErikKalkoken/aa-package-monitor/-/blob/master/LICENSE)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![chat](https://img.shields.io/discord/790364535294132234)](https://discord.gg/zmh52wnfvM)

## Contents

- [Overview](#overview)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [Updating](#updating)
- [User Guide](#user-guide)
- [Settings](#settings)
- [Permissions](#permissions)
- [Management Commands](#management-commands)
- [Change Log](CHANGELOG.md)

## Overview

Package Monitor is an app for Alliance Auth that helps you keep your installation up-to-date. It shows you all installed distributions packages and will automatically notify you, when there are updates available.

Features:

- Shows list of installed distributions packages with related Django apps (if any)
- Identifies new valid releases for installed packages on PyPI
- Notifies user which installed packages are outdated and should be updated
- Shows the number of outdated packages as badge in the sidebar
- Takes into account the requirements of all installed packages and the current Python version when recommending updates
- Option to add distribution pages to the monitor which are not related to Django apps
- Option to show all known distribution packages (as opposed to only the ones that belong to installed Django apps)
- Copy the respective command for a package update to your clipboard directly from the package list
- Can automatically notify admins when there is an update available for a currently installed package
- Supported languages: English :us:, German :de: and Russian :ru:

>**Hint**: Update notifications are sent as AA notifications to all admins. We recommend using [Discord Notify](https://gitlab.com/ErikKalkoken/aa-discordnotify) to automatically forward those notifications to Discord as DMs.

## Screenshots

![screenshot](https://cdn.imgpile.com/f/aTDpYjJ_xl.png)

## Installation

### Step 1 - Check Preconditions

Please make sure you meet all preconditions before proceeding:

- Package Monitor is a plugin for [Alliance Auth](https://gitlab.com/allianceauth/allianceauth). If you don't have Alliance Auth running already, please install it first before proceeding. (see the official [AA installation guide](https://allianceauth.readthedocs.io/en/latest/installation/auth/allianceauth/) for details)

### Step 2 - Install app

Make sure you are in the virtual environment (venv) of your Alliance Auth installation. Then install the newest release from PYPI:

```bash
pip install aa-package-monitor
```

### Step 3 - Configure settings

Add `'package_monitor'` to `INSTALLED_APPS`.

Add the following lines to your `local.py` to enable regular checking for updates:

```Python
CELERYBEAT_SCHEDULE['package_monitor_update_distributions'] = {
    'task': 'package_monitor.tasks.update_distributions',
    'schedule': crontab(minute='*/60'),
}
```

Finally, please also take a moment to consider how often you want to receive update notifications. The default is immediate, but you can also chose to receive notifications after a timeout, e.g. only once per 24 hours or once per week. If you choose a timeout you can also choose to get repeated notifications about the same updates, like a reminder. For more details please see the [Settings](#settings).

### Step 4 - Finalize installation

Run migrations & copy static files

```bash
python manage.py migrate
python manage.py collectstatic
```

Restart your supervisor services for Auth

### Step 5 - Initial data load

Last, but not least perform an initial data load of all distribution packages by running the following command:

```bash
python manage.py packagemonitorcli refresh
```

## Updating

```bash
pip install -U aa-package-monitor

python manage.py collectstatic

python manage.py migrate
```

Finally restart your AA supervisor services.

## User Guide

This section explains how to use the app.

### Terminology

To avoid any confusion here are our definitions of some important terms:

- **App**: A Django application. An app is always part of a distribution package
- **Distribution package** A Python package that can be installed via pip or setuptools. Distribution packages can contain several apps.
- **Requirement**: A requirement is a condition that distribution packages can define to specify dependencies to environments or other distribution packages with specific versions. For example the distribution package django-eveuniverse can have the requirement `"django-esi>=2.0"`, which means is requires the package django-esi in at leasts version 2.0

### Operation modes

You can run Package Monitor in one of two modes:

- Keep everything updated
- Keep apps and selected distribution packages updated

#### Keep everything updated

In this mode Package Monitor will monitor all installed distribution packages. In this mode you will be informed you about updates to any of your distribution packages.

This is the default operation mode.

#### Keep apps and selected distribution packages updated

With this mode Package Monitor will monitor only those distribution packages that contain actually installed Django apps. In this mode you will be informed if there is an update to any of your apps. Note that in mode A other installed distributions packages will not be shown.

To activate this mode set `PACKAGE_MONITOR_SHOW_ALL_PACKAGES` to `False` in your local settings.

You can also add some additional distributions to be monitored. For example you might want to add celery.

See also [Settings](#settings) for an overview of all settings.

### Latest version

Package Monitor will automatically determine a latest version for a distribution package from PyPI. Note that this can differ from the latest version shown on PyPI, because of additional considerations:

First, Package Monitor will take into account all requirements of all installed distribution packages. For example if the Alliance Auth has the requirement "Django<3", then it will only show Django 2.x as latest, since Django 3.x would not fullfil the requirement set by Alliance Auth.

Second, Package Monitor will in general ignore pre-releases and consider stable releases for updates only. The only exception is if the current package also is a pre release. For example you may have Black installed as beta release, therefore the app will also suggest newer beta releases.

## Settings

Here is a list of available settings for this app. They can be configured by adding them to your AA settings file (`local.py`).

Note that all settings are optional and the app will use the documented default settings if they are not used.

Name|Description|Default
--|--|--
Name|Description|Default
--|--|--
`PACKAGE_MONITOR_CUSTOM_REQUIREMENTS`|List of custom requirements that all potential updates are checked against. Example: ["gunicorn<20"]|`[]`
`PACKAGE_MONITOR_EXCLUDE_PACKAGES`|Names of distribution packages to be excluded.|`[]`
`PACKAGE_MONITOR_INCLUDE_PACKAGES`|Names of additional distribution packages to be monitored.|`[]`
`PACKAGE_MONITOR_NOTIFICATIONS_ENABLED`|Whether to notify when an update is available for a currently installed distribution package.|`False`
`PACKAGE_MONITOR_NOTIFICATIONS_MAX_DELAY`|Maximum delay in seconds between the scheduled event for firing a notification and the time the notification is issued.  This value should be synchronized with the timing of the recurring task.|`5400`
`PACKAGE_MONITOR_NOTIFICATIONS_REPEAT`|Whether to repeat notifying about the same updates.|`False`
`PACKAGE_MONITOR_NOTIFICATIONS_SCHEDULE`|When to send notifications about updates. If not set, update notifications can be send every time the regular task runs.  The schedule can be defined in natural language. Examples: "every day at 10:00", "every saturday at 18:00", "every first saturday every month at 15:00". For more information about the syntax please see: [recurrent package](https://github.com/kvh/recurrent)|``
`PACKAGE_MONITOR_PROTECTED_PACKAGES`|Names of protected packages.  Updates can include requirements for updating other packages, which can potentially break the current AA installation.  For example: You have Django 4.2 installed and an update to a package requires Django 5 or higher. Then installing that package may break your installation.  When enabled Package Monitor will not show updates, which would cause an indirect update of a protected package.  And empty list disables this feature.|`['allianceauth', 'django']`
`PACKAGE_MONITOR_SHOW_ALL_PACKAGES`|Whether to show all distribution packages, as opposed to only showing packages that contain Django apps.|`True`
`PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES`|Whether to show distribution packages installed as editable.  Since version information about editable packages is often outdated, this type of packages are not shown by default.|`False`

## Permissions

This is an overview of all permissions used by this app. Note that all permissions are in the "general" section.

Name | Purpose | Code
-- | -- | --
Can access this app and view | User can access the app and also request updates to the list of distribution packages |  `general.basic_access`

## Management Commands

This app also provides a CLI tool. This tool gives you access to additional features, which are meant to support admins  support with analyzing potential issues.

Please run the following command to see all available features:

```sh
python manage.py packagemonitorcli -h
```
