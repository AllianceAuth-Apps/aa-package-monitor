from unittest.mock import patch

from django.test import RequestFactory
from django.urls import reverse

from app_utils.testdata_factories import UserMainFactory
from app_utils.testing import NoSocketsTestCase, json_response_to_python

from package_monitor import views

from .factories import DistributionFactory

MODULE_PATH_VIEWS = "package_monitor.views"
MODULE_PATH_MANAGERS = "package_monitor.managers"


@patch(MODULE_PATH_MANAGERS + ".PACKAGE_MONITOR_SHOW_ALL_PACKAGES", True)
@patch(MODULE_PATH_MANAGERS + ".PACKAGE_MONITOR_INCLUDE_PACKAGES", [])
class TestPackageList(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.user = UserMainFactory(permissions__=["package_monitor.basic_access"])
        cls.factory = RequestFactory()

    def test_index_view(self):
        # given
        request = self.factory.get(reverse("package_monitor:index"))
        request.user = self.user
        # when
        response = views.index(request)
        # then
        self.assertEqual(response.status_code, 200)

    def test_list_view_all(self):
        # given
        DistributionFactory(name="alpha")
        DistributionFactory(name="bravo")
        request = self.factory.get(reverse("package_monitor:package_list_data"))
        request.user = self.user
        # when
        response = views.package_list_data(request)
        # then
        self.assertEqual(response.status_code, 200)
        package_names = [x["name"] for x in json_response_to_python(response)]
        self.assertListEqual(package_names, ["alpha", "bravo"])

    def test_list_view_outdated(self):
        # given
        DistributionFactory(name="alpha")
        DistributionFactory(
            name="bravo",
            is_outdated=True,
            installed_version="1.0.0",
            latest_version="1.1.0",
        )
        request = self.factory.get(
            reverse("package_monitor:package_list_data"), data={"filter": "outdated"}
        )
        request.user = self.user
        # when
        response = views.package_list_data(request)
        # then
        self.assertEqual(response.status_code, 200)
        package_names = [x["name"] for x in json_response_to_python(response)]
        self.assertListEqual(package_names, ["bravo"])

    def test_list_view_current(self):
        # given
        DistributionFactory(name="alpha")
        DistributionFactory(
            name="bravo",
            is_outdated=True,
            installed_version="1.0.0",
            latest_version="1.1.0",
        )
        request = self.factory.get(
            reverse("package_monitor:package_list_data"), data={"filter": "current"}
        )
        request.user = self.user
        # when
        response = views.package_list_data(request)
        # then
        self.assertEqual(response.status_code, 200)
        package_names = [x["name"] for x in json_response_to_python(response)]
        self.assertListEqual(package_names, ["alpha"])

    def test_list_view_unknown(self):
        # given
        DistributionFactory(name="alpha")
        DistributionFactory(name="charlie", is_outdated=None)
        request = self.factory.get(
            reverse("package_monitor:package_list_data"), data={"filter": "unknown"}
        )
        request.user = self.user
        # when
        response = views.package_list_data(request)
        # then
        self.assertEqual(response.status_code, 200)
        package_names = [x["name"] for x in json_response_to_python(response)]
        self.assertListEqual(package_names, ["charlie"])

    @patch(MODULE_PATH_VIEWS + ".Distribution.objects.update_all")
    def test_refresh_distributions_view(self, mock_update_all):
        mock_update_all.return_value = 1

        request = self.factory.get(reverse("package_monitor:refresh_distributions"))
        request.user = self.user
        response = views.refresh_distributions(request)
        self.assertEqual(response.status_code, 200)
