"""Managers for Package Monitor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Set

from packaging.version import parse as version_parse

from django.db import models

from allianceauth.services.hooks import get_extension_logger
from app_utils.allianceauth import notify_admins
from app_utils.logging import LoggerAddTag

from . import __title__
from .app_settings import (
    PACKAGE_MONITOR_EXCLUDE_PACKAGES,
    PACKAGE_MONITOR_INCLUDE_PACKAGES,
    PACKAGE_MONITOR_SHOW_ALL_PACKAGES,
    PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES,
)
from .core.distribution_packages import (
    DistributionPackage,
    compile_package_requirements,
    gather_distribution_packages,
    update_packages_from_pypi,
)

if TYPE_CHECKING:
    from .models import Distribution

TERMINAL_MAX_LINE_LENGTH = 4095

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class DistributionQuerySet(models.QuerySet):
    """QuerySets for Distribution."""

    def outdated_count(self) -> int:
        """Return count of outdated packages."""
        return self.filter(is_outdated=True).count()

    def build_install_command(self) -> str:
        """Build install command from all distribution packages in this query."""
        result = ""
        for dist in self.exclude(latest_version=""):
            version_string = dist.pip_install_version
            if len(result) + len(version_string) + 1 > TERMINAL_MAX_LINE_LENGTH:
                break
            result += f"{version_string} "
        return result.strip()

    def filter_visible(self) -> models.QuerySet:
        """Filter to include visible packages only based on current settings."""
        if PACKAGE_MONITOR_SHOW_ALL_PACKAGES:
            qs = self.all()
        else:
            qs = self.filter(has_installed_apps=True)
        if PACKAGE_MONITOR_INCLUDE_PACKAGES:
            qs |= self.filter(name__in=PACKAGE_MONITOR_INCLUDE_PACKAGES)
        if PACKAGE_MONITOR_EXCLUDE_PACKAGES:
            qs = qs.exclude(name__in=PACKAGE_MONITOR_EXCLUDE_PACKAGES)
        if not PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES:
            qs = qs.exclude(is_editable=True)
        return qs

    def names(self) -> Set[str]:
        """Return QS as set of names."""
        return set(self.values_list("name", flat=True))


class DistributionManagerBase(models.Manager):
    """Manager for Distribution."""

    def update_all(self) -> int:
        """Update the list of relevant distribution packages in the database."""
        logger.info(
            f"Started refreshing approx. {self.count()} distribution packages..."
        )
        packages = gather_distribution_packages()
        requirements = compile_package_requirements(packages)
        update_packages_from_pypi(packages, requirements)
        self._save_packages(packages=packages, requirements=requirements)
        packages_count = len(packages)
        logger.info(f"Completed refreshing {packages_count} distribution packages")
        return packages_count

    def _save_packages(
        self, packages: Dict[str, DistributionPackage], requirements: dict
    ) -> None:
        """Save the given package information into the model."""

        for package_name, package in packages.items():
            logger.debug("Updating package: %s", package)
            if package_name in requirements:
                used_by = [
                    {
                        "name": package_name,
                        "homepage_url": (
                            packages[package_name].homepage_url
                            if packages.get(package_name)
                            else ""
                        ),
                        "requirements": [str(obj) for obj in package_requirements],
                    }
                    for package_name, package_requirements in requirements[
                        package_name
                    ].items()
                ]
            else:
                used_by = []

            defaults = {
                "apps": sorted(package.apps, key=str.casefold),
                "used_by": used_by,
                "installed_version": package.current,
                "latest_version": package.latest,
                "is_outdated": package.is_outdated(),
                "is_editable": package.is_editable,
                "description": package.summary,
                "website_url": package.homepage_url,
            }
            self.update_or_create(name=package.name, defaults=defaults)

        package_names = {obj.name for obj in packages.values()}
        self.exclude(name__in=package_names).delete()

    def send_update_notification(
        self: models.QuerySet[Distribution],
        show_editable: bool,
        should_repeat: bool = False,
    ) -> None:
        """Send notification to admins to inform about new versions."""
        selected = self._filter_dist_to_notify(
            show_editable=show_editable, should_repeat=should_repeat
        )
        if selected:
            self._send_update_notification(selected)

    def _filter_dist_to_notify(
        self: models.QuerySet[Distribution],
        show_editable: bool,
        should_repeat: bool,
    ) -> List[Distribution]:
        selected = []
        for dist in self.order_by("name"):
            if dist.is_editable and not show_editable:
                continue
            if not dist.installed_version or not dist.latest_version:
                continue
            installed = version_parse(dist.installed_version)
            latest = version_parse(dist.latest_version)
            if latest <= installed:
                continue
            if not should_repeat and dist.latest_notified_version:
                notified = version_parse(dist.latest_notified_version)
                if notified >= latest:
                    continue
            selected.append(dist)
        return selected

    def _send_update_notification(self, distributions: List[Distribution]):
        count = len(distributions)
        update_text = f"{count} update" if count == 1 else f"{count} updates"
        title = f"Package Monitor: {update_text} available"
        update_text = "is one update" if count == 1 else f"are {count} updates"
        message = f"There {update_text} available:\n"
        for dist in distributions:
            message += (
                f"- {dist.name} {dist.installed_version} => {dist.latest_version}\n"
            )

        notify_admins(message=message, title=title)

        for dist in distributions:
            dist.latest_notified_version = dist.latest_version
            dist.save(update_fields={"latest_notified_version"})


DistributionManager = DistributionManagerBase.from_queryset(DistributionQuerySet)
