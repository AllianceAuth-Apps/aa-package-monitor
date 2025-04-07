from unittest import mock

from aioresponses import aioresponses

from django.test import TestCase, override_settings

from package_monitor import tasks
from package_monitor.core import pypi
from package_monitor.core.distribution_packages import DistributionPackage
from package_monitor.models import Distribution

from .factories import MetadataDistributionStubFactory, PypiFactory, PypiReleaseFactory

CORE_PATH = "package_monitor.core.distribution_packages"
CORE_HELPERS_PATH = "package_monitor.core.metadata_helpers"
MANAGERS_PATH = "package_monitor.managers"
TASKS_PATH = "package_monitor.tasks"


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@mock.patch(TASKS_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_ENABLED", False)
@mock.patch(CORE_HELPERS_PATH + ".django_apps", spec=True)
@mock.patch(CORE_PATH + ".importlib_metadata.distributions", spec=True)
class TestUpdatePackagesFromPyPi(TestCase):
    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        # workaround to remove obj which is not cleaned up
        Distribution.objects.all().delete()

    def setUp(self) -> None:
        pypi.clear_cache()

    @aioresponses()
    def test_should_update_packages(
        self, mock_distributions, mock_django_apps, requests_mocker
    ):
        # given
        dist_alpha = MetadataDistributionStubFactory(name="alpha", version="1.0.0")
        mock_distributions.return_value = [dist_alpha]
        mock_django_apps.get_app_configs.return_value = []

        pypi_alpha = PypiFactory(
            distribution=DistributionPackage.create_from_metadata_distribution(
                dist_alpha
            )
        )
        pypi_alpha.info.version = "1.1.0"
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory()]
        requests_mocker.get(
            "https://pypi.org/pypi/alpha/json", payload=pypi_alpha.asdict()
        )
        requests_mocker.get(
            "https://pypi.org/pypi/alpha/1.1.0/json", payload=pypi_alpha.asdict()
        )

        # when
        tasks.update_distributions(disable_jitter=True)

        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.get(name="alpha")
        self.assertEqual(obj.latest_version, "1.1.0")
