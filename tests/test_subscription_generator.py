"""Tests for powerbi_import.subscription_generator."""

import json
import os
import tempfile
import unittest

from powerbi_import.subscription_generator import (
    SubscriptionRule,
    convert_qlik_alerts,
    convert_qlik_tasks,
    generate_subscriptions_json,
    generate_subscriptions_powershell,
)


class TestSubscriptionRule(unittest.TestCase):
    def test_to_dict(self):
        rule = SubscriptionRule(
            name='Test Alert',
            report_name='Sales Report',
            schedule_type='daily',
            schedule_time='09:00',
        )
        d = rule.to_dict()
        self.assertEqual(d['name'], 'Test Alert')
        self.assertEqual(d['schedule']['type'], 'daily')

    def test_weekly_includes_days(self):
        rule = SubscriptionRule(
            name='Weekly',
            report_name='Report',
            schedule_type='weekly',
            days_of_week=['Monday', 'Friday'],
        )
        d = rule.to_dict()
        self.assertIn('daysOfWeek', d['schedule'])


class TestConvertAlerts(unittest.TestCase):
    def test_basic_alert(self):
        alerts = [{
            'name': 'High Sales',
            'condition': {'measure': 'Total Sales', 'operator': 'above', 'threshold': 1000},
            'trigger': {'type': 'daily', 'time': '08:00'},
            'recipients': ['user@example.com'],
        }]
        rules = convert_qlik_alerts(alerts, report_name='Sales')
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].name, 'High Sales')
        self.assertIsNotNone(rules[0].condition)

    def test_empty_alerts(self):
        self.assertEqual(convert_qlik_alerts([]), [])

    def test_string_recipients(self):
        alerts = [{
            'name': 'Test',
            'trigger': {},
            'recipients': 'a@b.com;c@d.com',
        }]
        rules = convert_qlik_alerts(alerts)
        self.assertEqual(len(rules[0].recipients), 2)


class TestConvertTasks(unittest.TestCase):
    def test_basic_task(self):
        tasks = [{
            'name': 'Reload Sales',
            'triggers': [{'type': 'daily', 'time': '06:00'}],
            'recipients': ['admin@example.com'],
        }]
        rules = convert_qlik_tasks(tasks, report_name='Sales')
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].schedule_type, 'daily')

    def test_multiple_triggers(self):
        tasks = [{
            'name': 'Multi',
            'triggers': [
                {'type': 'daily', 'time': '06:00'},
                {'type': 'on_reload'},
            ],
        }]
        rules = convert_qlik_tasks(tasks)
        self.assertEqual(len(rules), 2)

    def test_single_trigger_dict(self):
        tasks = [{
            'name': 'Single',
            'trigger': {'type': 'weekly'},
        }]
        rules = convert_qlik_tasks(tasks)
        self.assertEqual(len(rules), 1)


class TestGenerateJson(unittest.TestCase):
    def test_output_string(self):
        rules = [SubscriptionRule(name='Test', report_name='Report')]
        result = generate_subscriptions_json(rules)
        data = json.loads(result)
        self.assertEqual(data['subscription_count'], 1)

    def test_output_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'subs.json')
            rules = [SubscriptionRule(name='Test', report_name='Report')]
            generate_subscriptions_json(rules, output_path=path)
            self.assertTrue(os.path.exists(path))


class TestGeneratePowershell(unittest.TestCase):
    def test_script_content(self):
        rules = [SubscriptionRule(name='Test', report_name='Report')]
        script = generate_subscriptions_powershell(rules)
        self.assertIn('Connect-PowerBIServiceAccount', script)
        self.assertIn('Test', script)

    def test_output_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'setup.ps1')
            rules = [SubscriptionRule(name='Test', report_name='Report')]
            generate_subscriptions_powershell(rules, output_path=path)
            self.assertTrue(os.path.exists(path))


if __name__ == '__main__':
    unittest.main()
