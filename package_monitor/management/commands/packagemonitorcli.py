"""CLI commands for Package Monitor."""

import datetime as dt
import json
import sys
from enum import Enum

import humanize
import importlib_metadata

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db.models import QuerySet

from package_monitor import __version__
from package_monitor.core import distribution_packages
from package_monitor.models import Distribution

try:
    import yaml
except ImportError:
    yaml = None

COMMAND = "command"

EXCLUDED_METADATA_FIELDS = {"description", "description_content_type", "license"}
"""Metadata fields excluded by default in the dump command."""


class SubCommand(str, Enum):
    DUMP = "dump"
    INSTALL = "install"
    OUTDATED = "outdated"
    REFRESH = "refresh"
    VERSION = "version"


class Command(BaseCommand):
    help = "A tool for monitoring distribution packages from CLI."

    def add_arguments(self, parser: CommandParser) -> None:
        subparsers = parser.add_subparsers(
            dest=COMMAND,
            required=True,
            title="commands",
            help="available commands",
        )
        dump = subparsers.add_parser(
            SubCommand.DUMP.value,
            help="Dump a list of all installed distribution packages and current import paths to stdout",
        )
        dump.add_argument(
            "-f",
            "--format",
            default="yaml",
            choices=["json", "yaml"],
            help="Data format. (Default: yaml)",
        )
        dump.add_argument(
            "--all-meta-fields",
            action="store_true",
            help=f"Do not exclude any metadata fields. By default these are not included: {EXCLUDED_METADATA_FIELDS}",
        )
        dump.add_argument(
            "--all-import-paths",
            action="store_true",
            help=(
                "Do not exclude any import paths. "
                f"By default these are not included: {distribution_packages.EXCLUDED_IMPORT_PATHS}"
            ),
        )
        dump.add_argument(
            "-r",
            "--resolve-files",
            action="store_true",
            help="Resolve paths for all files",
        )
        subparsers.add_parser(
            SubCommand.INSTALL.value,
            help=(
                "Print parameters for installing outdated packages. "
                "Usage: pip install $(python manage.py packagemonitorcli install)"
            ),
        )
        subparsers.add_parser(
            SubCommand.OUTDATED.value,
            help="Show outdated distribution packages",
        )
        subparsers.add_parser(
            SubCommand.REFRESH.value,
            help="Refresh list of distribution packages",
        )
        subparsers.add_parser(
            SubCommand.VERSION.value,
            help="Show version of package_manager app",
        )

    def handle(self, *args, **options):
        command = options[COMMAND]
        if command == SubCommand.DUMP:
            self.dump(
                format=options["format"],
                all_meta_fields=options["all_meta_fields"],
                all_import_paths=options["all_import_paths"],
                resolve_files=options["resolve_files"],
            )
        elif command == SubCommand.REFRESH:
            self.refresh()
        elif command == SubCommand.INSTALL:
            self.install()
        elif command == SubCommand.OUTDATED:
            self.outdated()
        elif command == SubCommand.VERSION:
            self.version()
        else:
            raise NotImplementedError(command)

    def dump(
        self,
        format: str,
        all_meta_fields: bool,
        resolve_files: bool,
        all_import_paths: bool,
    ):
        if all_import_paths:
            import_paths = sys.path
        else:
            import_paths = distribution_packages.relevant_import_paths()
        duplicate_count = 0
        packages = {}
        for d in importlib_metadata.distributions(path=import_paths):
            if resolve_files:
                files = [str(f.locate()) for f in d.files]
            else:
                files = [str(f) for f in d.files]
            metadata = d.metadata.json
            if not all_meta_fields and isinstance(metadata, dict):
                metadata = {
                    k: v
                    for k, v in metadata.items()
                    if k not in EXCLUDED_METADATA_FIELDS
                }
            package = {
                "name": d.name,
                "normalized_name": d._normalized_name,
                "version": d.version,
                "requires": d.requires,
                "files": files,
                "metadata": metadata,
            }
            name = d._normalized_name
            while True:
                if name not in packages:
                    break
                name += "_"
                package["duplicate"] = True
                duplicate_count += 1
            packages[name] = package

        import_paths.sort()
        excluded_fields = list(EXCLUDED_METADATA_FIELDS) if not all_meta_fields else []
        excluded_fields.sort()
        excluded_paths = [p for p in sys.path if p not in set(import_paths)]
        excluded_paths.sort()
        data = {
            "_meta": {
                "excluded_metadata_fields": excluded_fields,
                "excluded_import_paths": excluded_paths,
                "package_monitor_version": __version__,
                "package_count": len(packages),
                "import_path_count": len(import_paths),
                "duplicate_count": duplicate_count,
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(
                    timespec="seconds"
                ),
            },
            "_python": {
                "import_paths": import_paths,
                "version": sys.version,
            },
            "packages": packages,
        }

        if format == "json":
            o = json.dumps(data, sort_keys=True, indent=4)
        elif format == "yaml":
            o = yaml.dump(data)
        else:
            raise NotImplementedError(format)
        self.stdout.write(o)

    def refresh(self):
        package_count = Distribution.objects.count()
        self.stdout.write(
            f"Started refreshing data for currently {package_count} distribution packages...."
        )
        package_count = Distribution.objects.update_all()
        outdated_count = Distribution.objects.filter_visible().outdated_count()
        self.stdout.write(
            f"{outdated_count} / {package_count} distribution packages are outdated. "
        )
        self.stdout.write(self.style.SUCCESS("DONE"))

    def outdated(self):
        obj = Distribution.objects.first()
        updated_at = obj.updated_at if obj else None
        outdated_count = (
            Distribution.objects.filter_visible()
            .exclude(latest_version="")
            .outdated_count()
        )
        package_count = Distribution.objects.count()
        last_checked = humanize.naturaltime(updated_at) if updated_at else "?"
        self.stdout.write(
            f"{outdated_count} / {package_count} distribution packages are outdated. "
            f"Last checked {last_checked}"
        )
        if outdated_count == 0:
            return

        self.stdout.write()
        qs: QuerySet[Distribution] = (
            Distribution.objects.filter_visible()
            .exclude(latest_version="")
            .filter(is_outdated=True)
            .order_by("name")
        )
        for d in qs:
            self.stdout.write(
                f"{d.name} {d.latest_version} [upgradeable from: {d.latest_version}]"
            )

    def install(self):
        outdated_count = (
            Distribution.objects.filter_visible()
            .exclude(latest_version="")
            .outdated_count()
        )
        if outdated_count == 0:
            raise CommandError("No outdated packages")

        command = (
            Distribution.objects.filter_visible()
            .exclude(latest_version="")
            .filter(is_outdated=True)
            .order_by("name")
            .build_install_command()
        )
        self.stdout.write(command)

    def version(self):
        self.stdout.write(__version__)
