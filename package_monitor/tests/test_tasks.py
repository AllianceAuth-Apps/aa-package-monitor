import datetime as dt
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils.timezone import now

from package_monitor import tasks

MODULE_PATH = "package_monitor.tasks"
UTC = dt.timezone.utc


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODULE_PATH + ".cache.get", spec=True)
@patch(MODULE_PATH + ".schedule.is_notification_due")
class TestShouldSendNotifications(TestCase):
    def test_should_send_notification_when_due(self, is_notification_due, cache_get):
        # given
        is_notification_due.return_value = True
        last_report = (dt.datetime(2024, 7, 10, 10, 0, 0, tzinfo=UTC),)
        cache_get.return_value = last_report
        # when
        with patch(MODULE_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_ENABLED", True), patch(
            MODULE_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_SCHEDULE", "my schedule"
        ), patch(MODULE_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_MAX_DELAY", 42):
            result = tasks._should_send_notifications()
        # then
        self.assertTrue(result)
        _, kwargs = is_notification_due.call_args
        self.assertEqual(kwargs["schedule_text"], "my schedule")
        self.assertEqual(kwargs["last_report"], last_report)
        self.assertEqual(kwargs["max_delay"], 42)

    def test_should_not_send_notification_when_not_due(
        self, is_notification_due, cache_get
    ):
        # given
        is_notification_due.return_value = False
        last_report = (dt.datetime(2024, 7, 10, 10, 0, 0, tzinfo=UTC),)
        cache_get.return_value = last_report
        # when
        with patch(MODULE_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_ENABLED", True):
            result = tasks._should_send_notifications()
        # then
        self.assertFalse(result)

    def test_should_not_send_notification_when_disabled(
        self, is_notification_due, cache_get
    ):
        # when
        with patch(MODULE_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_ENABLED", False):
            result = tasks._should_send_notifications()
        # then
        self.assertFalse(result)


@patch(MODULE_PATH + ".cache.set", spec=True)
@patch(MODULE_PATH + ".Distribution.objects.send_update_notification")
class TestSendUpdateNotifications(TestCase):
    def test_can_send_notifications(self, send_update_notification, cache_set):
        # when
        with patch(
            MODULE_PATH + ".PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES", False
        ), patch(MODULE_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_REPEAT", False):
            tasks.send_update_notification()
        # then
        self.assertTrue(send_update_notification.called)
        _, kwargs = send_update_notification.call_args
        self.assertFalse(kwargs["should_repeat"])
        self.assertFalse(kwargs["show_editable"])
        self.assertTrue(cache_set.called)
        _, kwargs = cache_set.call_args
        self.assertAlmostEqual(kwargs["value"], now(), delta=dt.timedelta(seconds=10))


@patch(MODULE_PATH + ".Distribution")
@patch(MODULE_PATH + "._should_send_notifications")
@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestUpdateDistributions(TestCase):
    def test_should_update_and_notify(self, should_send_notifications, Distribution):
        # given
        should_send_notifications.return_value = True
        # when
        tasks.update_distributions(disable_jitter=True)
        # then
        self.assertTrue(Distribution.objects.update_all.called)
        self.assertTrue(Distribution.objects.send_update_notification.called)

    def test_should_update_and_not_notify(
        self, should_send_notifications, Distribution
    ):
        # given
        should_send_notifications.return_value = False
        # when
        tasks.update_distributions(disable_jitter=True)
        # then
        self.assertTrue(Distribution.objects.update_all.called)
        self.assertFalse(Distribution.objects.send_update_notification.called)
