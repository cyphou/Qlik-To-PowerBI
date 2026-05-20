"""Tests for powerbi_import.migration_planner."""

import unittest

from powerbi_import.migration_planner import (
    AppAssessment,
    MigrationPlan,
    estimate_effort,
    classify_complexity,
    assign_waves,
    map_workspaces,
    build_migration_plan,
)


class TestEstimateEffort(unittest.TestCase):
    def test_base_effort(self):
        self.assertGreater(estimate_effort(0, 0, 0), 0)

    def test_scales_with_visuals(self):
        e1 = estimate_effort(10, 0, 0)
        e2 = estimate_effort(20, 0, 0)
        self.assertGreater(e2, e1)

    def test_rls_penalty(self):
        e_no_rls = estimate_effort(5, 5, 1, has_rls=False)
        e_rls = estimate_effort(5, 5, 1, has_rls=True)
        self.assertGreater(e_rls, e_no_rls)

    def test_custom_sql_penalty(self):
        e_no = estimate_effort(5, 5, 1, has_custom_sql=False)
        e_yes = estimate_effort(5, 5, 1, has_custom_sql=True)
        self.assertGreater(e_yes, e_no)


class TestClassifyComplexity(unittest.TestCase):
    def test_low(self):
        self.assertEqual(classify_complexity(2, 2, 0), 'low')

    def test_medium(self):
        self.assertEqual(classify_complexity(10, 10, 1), 'medium')

    def test_high(self):
        self.assertEqual(classify_complexity(20, 30, 3), 'high')

    def test_critical(self):
        self.assertEqual(classify_complexity(50, 50, 5, has_rls=True), 'critical')


class TestAssignWaves(unittest.TestCase):
    def test_single_wave(self):
        apps = [AppAssessment(app_name=f'app{i}', complexity='low') for i in range(5)]
        result = assign_waves(apps, max_per_wave=10)
        self.assertTrue(all(a.wave == 1 for a in result))

    def test_multiple_waves(self):
        apps = [AppAssessment(app_name=f'app{i}', complexity='low') for i in range(15)]
        result = assign_waves(apps, max_per_wave=10)
        self.assertEqual(max(a.wave for a in result), 2)

    def test_complexity_ordering(self):
        apps = [
            AppAssessment(app_name='critical', complexity='critical'),
            AppAssessment(app_name='low', complexity='low'),
            AppAssessment(app_name='medium', complexity='medium'),
        ]
        result = assign_waves(apps, max_per_wave=10)
        names = [a.app_name for a in result]
        self.assertEqual(names[0], 'low')
        self.assertEqual(names[-1], 'critical')


class TestMapWorkspaces(unittest.TestCase):
    def test_one_per_app(self):
        apps = [AppAssessment(app_name='Sales'), AppAssessment(app_name='HR')]
        result = map_workspaces(apps, 'one_per_app')
        self.assertNotEqual(result[0].workspace, result[1].workspace)

    def test_single(self):
        apps = [AppAssessment(app_name='A'), AppAssessment(app_name='B')]
        result = map_workspaces(apps, 'single')
        self.assertEqual(result[0].workspace, result[1].workspace)

    def test_by_wave(self):
        apps = [AppAssessment(app_name='A', wave=1), AppAssessment(app_name='B', wave=2)]
        result = map_workspaces(apps, 'by_wave')
        self.assertIn('Wave_1', result[0].workspace)
        self.assertIn('Wave_2', result[1].workspace)


class TestBuildMigrationPlan(unittest.TestCase):
    def test_empty(self):
        plan = build_migration_plan([])
        self.assertEqual(plan.total_effort_hours, 0)
        self.assertEqual(len(plan.apps), 0)

    def test_single_app(self):
        plan = build_migration_plan([{
            'app_name': 'Sales',
            'visual_count': 10,
            'measure_count': 5,
            'connector_count': 2,
        }])
        self.assertEqual(len(plan.apps), 1)
        self.assertGreater(plan.total_effort_hours, 0)
        self.assertEqual(plan.wave_count, 1)

    def test_multiple_apps(self):
        plan = build_migration_plan([
            {'app_name': 'A', 'visual_count': 5, 'measure_count': 5, 'connector_count': 1},
            {'app_name': 'B', 'visual_count': 50, 'measure_count': 50, 'connector_count': 5, 'has_rls': True},
        ])
        self.assertEqual(len(plan.apps), 2)
        self.assertGreater(plan.total_effort_hours, 0)

    def test_to_dict(self):
        plan = build_migration_plan([
            {'app_name': 'Test', 'visual_count': 3, 'measure_count': 2, 'connector_count': 1},
        ])
        d = plan.to_dict()
        self.assertEqual(d['total_apps'], 1)
        self.assertIn('apps', d)


class TestAppAssessment(unittest.TestCase):
    def test_to_dict(self):
        a = AppAssessment(app_name='Test', visual_count=10, effort_hours=5.5)
        d = a.to_dict()
        self.assertEqual(d['app_name'], 'Test')
        self.assertEqual(d['visual_count'], 10)
        self.assertEqual(d['effort_hours'], 5.5)


if __name__ == '__main__':
    unittest.main()
