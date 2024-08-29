from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from app_utils.testing import NoSocketsTestCase

PACKAGE_PATH = "package_monitor.management.commands"


@patch(PACKAGE_PATH + ".packagemonitorcli.Distribution.objects.update_all")
class TestRefresh(NoSocketsTestCase):
    def test_can_purge_all_data(self, mock_update_all):
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
