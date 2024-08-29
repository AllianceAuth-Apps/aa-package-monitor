"""Core logic for parsed distribution packages."""

import asyncio
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import aiohttp
import importlib_metadata
from packaging.markers import UndefinedComparison, UndefinedEnvironmentName
from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version
from packaging.version import parse as version_parse

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from package_monitor import __title__
from package_monitor.app_settings import (
    PACKAGE_MONITOR_CUSTOM_REQUIREMENTS,
    PACKAGE_MONITOR_PROTECTED_PACKAGES,
)

from . import metadata_helpers
from .pypi import fetch_project_from_pypi_async, fetch_pypi_releases

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

EXCLUDED_IMPORT_PATHS = {"/setuptools/_vendor"}
"""Exclude package from these import paths (check against ending)."""


@dataclass
class DistributionPackage:
    """A parsed distribution package."""

    name: str
    current: str
    is_editable: bool
    requirements: List[Requirement] = field(default_factory=list)
    apps: List[str] = field(default_factory=list)
    latest: str = ""
    homepage_url: str = ""
    summary: str = ""

    def __str__(self) -> str:
        return f"{self.name} {self.current}"

    @property
    def name_normalized(self) -> str:
        """Return normalized name."""
        return canonicalize_name(self.name)

    def is_outdated(self) -> Optional[bool]:
        """Is this package outdated?"""
        if self.current and self.latest:
            return version_parse(self.current) < version_parse(self.latest)
        return None

    def is_prerelease(self) -> bool:
        """Determine if this package is a prerelease."""
        current_version = version_parse(self.current)
        current_is_prerelease = (
            str(current_version) == str(self.current) and current_version.is_prerelease
        )
        return current_is_prerelease

    def _package_specifiers_from_requirements(self, requirements: dict) -> SpecifierSet:
        """Return consolidated specifiers for this package from all other packages."""
        s = SpecifierSet()
        if self.name_normalized in requirements:
            for _, specifier in requirements[self.name_normalized].items():
                s &= specifier
        return s

    async def update_from_pypi_async(
        self,
        session: aiohttp.ClientSession,
        requirements: dict,
        protected_packages_versions: dict,
        system_python: Version,
    ) -> bool:
        """Update latest version and URL from PyPI.

        Return True if update was successful, else False.
        """

        pypi_data = await fetch_project_from_pypi_async(session, name=self.name)
        if not pypi_data:
            return False

        updates = self._determine_available_updates(
            pypi_data_releases=pypi_data["releases"],
            package_specifiers=self._package_specifiers_from_requirements(requirements),
            system_python=system_python,
        )
        latest = await self._determine_latest_available_update(
            session,
            updates=updates,
            protected_packages_versions=protected_packages_versions,
        )

        self.latest = str(latest) if latest else self.current

        pypi_info = pypi_data.get("info")
        pypi_url = pypi_info.get("project_url", "") if pypi_info else ""
        self.homepage_url = pypi_url
        return True

    def _determine_available_updates(
        self,
        pypi_data_releases: dict,
        package_specifiers: SpecifierSet,
        system_python: Version,
    ) -> List[Version]:
        """Determine latest valid updates available on PyPI
        and return them as ascending list.
        """
        updates = []
        current_version = (
            version_parse(self.current) if self.current else Version("0.0.0")
        )
        for release, release_details in pypi_data_releases.items():
            version = to_version_or_none(release)
            if not version:
                logger.info(
                    "%s: Ignoring release with invalid version: %s",
                    self.name,
                    release,
                )
                continue

            if version.is_prerelease and not self.is_prerelease():
                continue

            if not is_version_in_specifiers(version, package_specifiers):
                continue

            if version <= current_version:
                continue

            release_detail = release_details[-1] if len(release_details) > 0 else None
            if release_detail:
                if release_detail["yanked"]:
                    continue

                if not self._required_python_matches(release_detail, system_python):
                    continue

            updates.append(version)

        return updates

    def _required_python_matches(
        self, release_detail, system_python_version: Version
    ) -> bool:
        if requires_python := release_detail.get("requires_python"):
            try:
                required_python_versions = SpecifierSet(requires_python)
            except InvalidSpecifier:
                logger.info(
                    "%s: Ignoring release with invalid requires_python: %s",
                    self.name,
                    requires_python,
                )
                return False

            if system_python_version not in required_python_versions:
                return False

        return True

    async def _determine_latest_available_update(
        self,
        session: aiohttp.ClientSession,
        updates: List[Version],
        protected_packages_versions: Dict[str, Version],
    ) -> Optional[Version]:
        """Determines latest available and valid update and returns it.
        Or return None if none are available.
        """
        if not updates:
            return None

        if protected_packages_versions:
            valid_updates = await self._gather_valid_updates(
                session, updates, protected_packages_versions
            )
        else:
            valid_updates = updates

        valid_updates.sort()
        latest = valid_updates.pop() if valid_updates else None
        return latest

    async def _gather_valid_updates(self, session, updates, package_versions):
        valid_updates = []
        releases = await fetch_pypi_releases(session, name=self.name, releases=updates)
        for release in releases:
            info = release.get("info")
            if not info:
                continue

            found_issue = False
            requires_dist = info.get("requires_dist") or []
            for req_str in requires_dist:
                try:
                    r = Requirement(req_str)
                except InvalidRequirement:
                    continue  # invalid requirements can be ignored

                if not is_marker_valid(r):
                    continue  # invalid requirements can be ignored

                if (name := canonicalize_name(r.name)) in package_versions:
                    v = package_versions[name]
                    if v not in r.specifier:
                        logger.debug(
                            "%s: Update does not match current packages: %s", self, r
                        )
                        found_issue = True
                        break  # exit at first found issue

            if found_issue:
                continue

            update = version_parse(info["version"])
            valid_updates.append(update)

        return valid_updates

    @classmethod
    def create_from_metadata_distribution(
        cls, dist: importlib_metadata.Distribution, disable_app_check=False
    ):
        """Create new object from a metadata distribution.

        This is the only place where we are accessing the importlib metadata API
        for a specific distribution package and are thus storing
        all needed information about that package in our new object.
        Should additional information be needed sometimes it should be fetched here too.
        """
        obj = cls(
            name=dist.name,
            current=dist.version,
            is_editable=metadata_helpers.is_distribution_editable(dist),
            requirements=metadata_helpers.parse_requirements(dist),
            summary=metadata_helpers.metadata_value(dist, "Summary"),
        )
        if not disable_app_check:
            obj.apps = metadata_helpers.identify_installed_django_apps(dist)
        return obj


def to_version_or_none(version_string: str) -> Optional[Version]:
    """Convert a version string to a Version object or return None if not possible."""
    try:
        version = version_parse(version_string)
    except InvalidVersion:
        return None

    if str(version) != str(version_string):
        return None

    return version


def is_version_in_specifiers(version: Version, specifiers: SpecifierSet) -> bool:
    """Return True if version is in specifies."""
    if len(specifiers) == 0:
        return True

    return version in specifiers


def gather_distribution_packages() -> Dict[str, DistributionPackage]:
    """Gather distribution packages and detect Django apps."""
    # The setuptools installation has it's own copy of packages.
    # To prevent importlib_metadata from reporting them as an installed package
    # in the current environment we need to exclude them
    packages = {}
    for dist in importlib_metadata.distributions(path=relevant_import_paths()):
        try:
            if not dist.name:
                continue
        except KeyError:
            logger.warning(
                "Ignoring corrupt distribution package: %s", dist.metadata.items()
            )
            continue
        obj = DistributionPackage.create_from_metadata_distribution(dist)
        name = obj.name_normalized
        if name in packages:
            logger.warning(
                "Found duplicate package. App is not able to determine "
                "what the correct installed version is: %s",
                name,
            )
        packages[name] = obj

    return packages


def compile_package_requirements(
    packages: Dict[str, DistributionPackage]
) -> Dict[str, Dict[str, SpecifierSet]]:
    """Consolidate requirements from all known distributions and known packages"""
    requirements = defaultdict(dict)

    # add requirements from all packages
    for package in packages.values():
        for requirement in package.requirements:
            _add_valid_requirement(requirements, requirement, package.name, packages)

    # add requirements from settings (if any)
    for requirement_string in PACKAGE_MONITOR_CUSTOM_REQUIREMENTS:
        try:
            requirement = Requirement(requirement_string)
        except InvalidRequirement:
            continue
        _add_valid_requirement(requirements, requirement, "CUSTOM", packages)

    return dict(requirements)


def _add_valid_requirement(
    requirements: dict, requirement: Requirement, package_name: str, packages: dict
):
    name = canonicalize_name(requirement.name)
    if name not in packages:
        return

    if not is_marker_valid(requirement):
        return

    requirements[name][package_name] = requirement.specifier


def is_marker_valid(requirement: Requirement) -> bool:
    """Report wether a requirement is valid based on it's marker.
    No marker means also True.
    """
    if not requirement.marker:
        return True

    try:
        return requirement.marker.evaluate()
    except (UndefinedEnvironmentName, UndefinedComparison):
        return False


def update_packages_from_pypi(
    packages: Dict[str, DistributionPackage], requirements: dict
) -> None:
    """Update packages with latest versions and URL from PyPI in accordance
    with the given requirements and updates the packages.
    """

    async def update_packages_from_pypi_async() -> None:
        """Update packages from PyPI concurrently."""
        system_python_version = determine_system_python_version()
        packages_versions = gather_protected_packages_versions(packages)
        async with aiohttp.ClientSession() as session:
            tasks = [
                asyncio.create_task(
                    package.update_from_pypi_async(
                        session=session,
                        requirements=requirements,
                        protected_packages_versions=packages_versions,
                        system_python=system_python_version,
                    )
                )
                for package in packages.values()
            ]
            await asyncio.gather(*tasks)

    asyncio.run(update_packages_from_pypi_async())


def determine_system_python_version() -> Version:
    """Return current Python version of this system."""
    result = version_parse(
        f"{sys.version_info.major}.{sys.version_info.minor}"
        f".{sys.version_info.micro}"
    )
    return result


def gather_protected_packages_versions(
    packages: Dict[str, DistributionPackage]
) -> Dict[str, Version]:
    """Return versions of protected packages
    or empty when no protected packages are defined or matching.
    """
    focus_packages = set(PACKAGE_MONITOR_PROTECTED_PACKAGES)
    if not focus_packages:
        return {}

    focus_names = {canonicalize_name(p) for p in focus_packages}
    result = {
        name: version_parse(p.current)
        for name, p in packages.items()
        if name in focus_names
    }
    return result


def relevant_import_paths() -> List[str]:
    """Return list of relevant import paths."""
    return [
        p for p in sys.path if not any(p.endswith(x) for x in EXCLUDED_IMPORT_PATHS)
    ]
