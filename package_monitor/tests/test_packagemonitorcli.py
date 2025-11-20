from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command

from app_utils.testing import NoSocketsTestCase

from package_monitor import __version__

from .factories import DistributionFactory

PACKAGE_PATH = "package_monitor.management.commands"
MANAGERS_PATH = "package_monitor.managers"


@patch(PACKAGE_PATH + ".packagemonitorcli.Distribution.objects.update_all")
class TestRefresh(NoSocketsTestCase):
    def test_can_refresh_packages(self, mock_update_all):
        mock_update_all.return_value = 0
        out = StringIO()
        call_command("packagemonitorcli", "refresh", stdout=out)
        self.assertTrue(mock_update_all.called)


class TestDump(NoSocketsTestCase):
    def test_can_dump_packages(self):
        out = StringIO()
        call_command("packagemonitorcli", "dump", stdout=out)
        o = out.getvalue()
        self.assertIn("pip", o)


@patch(MANAGERS_PATH + ".PACKAGE_MONITOR_SHOW_ALL_PACKAGES", True)
@patch(MANAGERS_PATH + ".PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES", False)
@patch(MANAGERS_PATH + ".PACKAGE_MONITOR_INCLUDE_PACKAGES", [])
@patch(MANAGERS_PATH + ".PACKAGE_MONITOR_EXCLUDE_PACKAGES", [])
class TestInstall(NoSocketsTestCase):
    def test_can_show_install_params(self):
        # given
        DistributionFactory(name="bravo", latest_version="2.1.0", is_outdated=True)
        DistributionFactory(name="alpha", latest_version="1.2.0", is_outdated=True)
        DistributionFactory(name="charlie", latest_version="2.1.0", is_outdated=False)
        out = StringIO()
        # when
        call_command("packagemonitorcli", "install", stdout=out)
        # then
        got = out.getvalue()
        self.assertEqual("alpha==1.2.0 bravo==2.1.0\n", got)

    def test_should_raise_error_when_no_outdated(self):
        # given
        DistributionFactory(name="charlie", latest_version="2.1.0", is_outdated=False)
        out = StringIO()
        # when/then
        with self.assertRaises(CommandError):
            call_command("packagemonitorcli", "install", stdout=out)

    @patch(PACKAGE_PATH + ".packagemonitorcli.Distribution.objects.update_all")
    def test_can_refresh_(self, mock_update_all):
        # given
        mock_update_all.return_value = 0
        DistributionFactory(name="bravo", latest_version="2.1.0", is_outdated=True)
        out = StringIO()
        # when
        call_command("packagemonitorcli", "install", "-r", stdout=out)
        # then
        got = out.getvalue()
        self.assertEqual("bravo==2.1.0\n", got)
        self.assertTrue(mock_update_all.called)


@patch(MANAGERS_PATH + ".PACKAGE_MONITOR_SHOW_ALL_PACKAGES", True)
@patch(MANAGERS_PATH + ".PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES", False)
@patch(MANAGERS_PATH + ".PACKAGE_MONITOR_INCLUDE_PACKAGES", [])
@patch(MANAGERS_PATH + ".PACKAGE_MONITOR_EXCLUDE_PACKAGES", [])
class TestOutdated(NoSocketsTestCase):
    def test_can_show_outdated(self):
        # given
        DistributionFactory(name="bravo", latest_version="2.1.0", is_outdated=True)
        DistributionFactory(name="alpha", latest_version="1.2.0", is_outdated=True)
        DistributionFactory(name="charlie", latest_version="2.1.0", is_outdated=False)
        # when
        out = StringIO()
        call_command("packagemonitorcli", "outdated", stdout=out)
        # then
        got = out.getvalue()
        self.assertIn("alpha", got)
        self.assertIn("bravo", got)
        self.assertNotIn("charlie", got)

    def test_should_handle_no_outdated(self):
        # given
        DistributionFactory(name="charlie", latest_version="2.1.0", is_outdated=False)
        # when
        out = StringIO()
        call_command("packagemonitorcli", "outdated", stdout=out)
        # then
        got = out.getvalue()
        self.assertNotIn("charlie", got)


class TestVersion(NoSocketsTestCase):
    def test_can_show_version(self):
        out = StringIO()
        call_command("packagemonitorcli", "version", stdout=out)
        o = out.getvalue()
        self.assertIn(__version__, o)
