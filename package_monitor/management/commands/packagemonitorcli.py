"""Commands for Package Monitor."""

import json

import importlib_metadata

from django.core.management.base import BaseCommand, CommandParser

from package_monitor import __title__, __version__
from package_monitor.models import Distribution

try:
    import yaml
except ImportError:
    yaml = None

COMMAND = "command"

EXCLUDED_FIELDS = {"description", "description_content_type", "license"}
"""Fields excluded by default in the dump command. But can be included with the --all flag."""


class Command(BaseCommand):
    help = "Package monitor CLI tool"

    def add_arguments(self, parser: CommandParser) -> None:
        subparsers = parser.add_subparsers(
            dest=COMMAND,
            required=True,
            title="commands",
            help="available commands",
        )
        dump = subparsers.add_parser(
            "dump",
            help="Dump a list of all installed packages to stdout",
        )
        dump.add_argument(
            "-f",
            "--format",
            default="json",
            choices=["json", "yaml"],
            help="Data format",
        )
        dump.add_argument(
            "-a",
            "--all",
            action="store_true",
            help=f"Include these normally omitted metadata fields: {EXCLUDED_FIELDS}",
        )
        subparsers.add_parser("refresh", help="Refresh distribution packages")

    def handle(self, *args, **options):
        command = options[COMMAND]
        if command == "dump":
            self.dump(options["format"], options["all"])
        elif command == "refresh":
            self.refresh()
        else:
            raise NotImplementedError(command)

    def dump(self, format: str, show_all: bool):
        distributions = {}
        for i, d in enumerate(importlib_metadata.distributions(), start=1):
            files = [str(f) for f in d.files]
            metadata = d.metadata.json
            if not show_all and isinstance(metadata, dict):
                metadata = {
                    k: v for k, v in metadata.items() if k not in EXCLUDED_FIELDS
                }
            x = {
                "name": d.name,
                "normalized_name": d._normalized_name,
                "version": d.version,
                "requires": d.requires,
                "files": files,
                "metadata": metadata,
            }
            k = d._normalized_name
            while True:
                if k not in distributions:
                    break
                k += "_"
                x["duplicate"] = True
            distributions[k] = x

        if format == "json":
            o = json.dumps(distributions, sort_keys=True, indent=4)
        elif format == "yaml":
            if not yaml:
                raise RuntimeError("PyYAMML not found.")
            o = yaml.dump(distributions)
        else:
            raise NotImplementedError(format)
        self.stdout.write(o)

    def refresh(self):
        self.stdout.write(f"*** {__title__} v{__version__} - Refresh Distributions ***")
        package_count = Distribution.objects.count()
        outdated_count = Distribution.objects.filter_visible().outdated_count()
        self.stdout.write(
            f"Started to refresh data for currently {package_count} distribution packages. "
            f"With {outdated_count} package(s) currently showing as outdated."
        )
        self.stdout.write("This can take a minute...Please wait")
        package_count = Distribution.objects.update_all()
        outdated_count = Distribution.objects.filter_visible().outdated_count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed refreshing data for {package_count} distribution packages. "
                f"Identified {outdated_count} outdated package(s)."
            )
        )
