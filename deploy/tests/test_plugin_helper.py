"""Activation is atomic from the administrator's point of view."""
import os
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import Mock

from deploy.plugin_helper import switch_release, ActivationError


class PluginActivationTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'demo'
        (self.root / 'releases' / '0.9.0').mkdir(parents=True)
        (self.root / 'releases' / '1.0.0').mkdir()
        (self.root / 'current').symlink_to('releases/0.9.0')

    def test_failed_health_restores_current(self):
        service = Mock()
        with self.assertRaises(ActivationError):
            switch_release(self.root, '1.0.0', service=service, health_check=lambda _: False, health_timeout=.01)
        self.assertEqual(os.readlink(self.root / 'current'), 'releases/0.9.0')
        self.assertEqual(service.call_count, 2)

    def test_repeat_activation_is_idempotent(self):
        service = Mock()
        switch_release(self.root, '1.0.0', service=service, health_check=lambda _: True)
        switch_release(self.root, '1.0.0', service=service, health_check=lambda _: True)
        self.assertEqual(os.readlink(self.root / 'current'), 'releases/1.0.0')
        service.assert_called_once_with('demo')

    def test_existing_target_with_failed_health_restarts(self):
        (self.root / 'current').unlink()
        (self.root / 'current').symlink_to('releases/1.0.0')
        probe = Mock(side_effect=[False, True])
        service = Mock()
        switch_release(self.root, '1.0.0', service=service, health_check=probe, health_timeout=1)
        service.assert_called_once_with('demo')

    def test_service_failure_restores_previous_release(self):
        service = Mock(side_effect=[RuntimeError('crashed'), None])
        with self.assertRaises(ActivationError):
            switch_release(self.root, '1.0.0', service=service, health_check=lambda _: True)
        self.assertEqual(os.readlink(self.root / 'current'), 'releases/0.9.0')

    def test_delayed_health_can_pass_without_rollback(self):
        probe = Mock(side_effect=[False, False, True])
        service = Mock()
        switch_release(self.root, '1.0.0', service=service, health_check=probe, health_timeout=1)
        self.assertEqual(os.readlink(self.root / 'current'), 'releases/1.0.0')
        self.assertEqual(probe.call_count, 3)
