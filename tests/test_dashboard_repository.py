import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from ai_editorial_team.infrastructure.persistence.postgres_dashboard_repository import (
    PostgresDashboardRepository,
    PostgresDashboardRepositoryError,
)


RUN_ID = UUID("12345678-1234-5678-1234-567812345678")
STARTED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


class PostgresDashboardRepositoryTests(unittest.TestCase):
    @patch(
        "ai_editorial_team.infrastructure.persistence."
        "postgres_dashboard_repository.psycopg.connect"
    )
    def test_get_latest_run_orders_by_started_at_desc(self, connect):
        connection, cursor = _mock_connection(connect)
        expected = {
            "id": RUN_ID,
            "started_at": STARTED_AT,
            "finished_at": None,
            "status": "running",
            "duration_seconds": None,
        }
        cursor.fetchone.return_value = expected
        repository = PostgresDashboardRepository("postgresql://test")

        actual = repository.get_latest_run()

        statement = cursor.execute.call_args.args[0]
        self.assertIs(actual, expected)
        self.assertIn("FROM runs", statement)
        self.assertIn("ORDER BY started_at DESC", statement)
        self.assertIn("LIMIT 1", statement)
        self.assertEqual(cursor.execute.call_args.kwargs, {"prepare": False})
        connect.assert_called_once_with(
            "postgresql://test",
            prepare_threshold=None,
            row_factory=dict_row,
        )
        connection.close.assert_called_once_with()

    @patch(
        "ai_editorial_team.infrastructure.persistence."
        "postgres_dashboard_repository.psycopg.connect"
    )
    def test_get_stories_filters_by_run_and_orders_by_rank(self, connect):
        _, cursor = _mock_connection(connect)
        expected = [
            {
                "rank": 1,
                "domain": "Sports",
                "headline": "Headline",
                "summary": "Summary",
                "editorial_reason": "Reason",
            }
        ]
        cursor.fetchall.return_value = expected
        repository = PostgresDashboardRepository("postgresql://test")

        actual = repository.get_stories(RUN_ID)

        statement, parameters = cursor.execute.call_args.args
        self.assertIs(actual, expected)
        self.assertIn("FROM stories", statement)
        self.assertIn("WHERE run_id = %s", statement)
        self.assertIn("ORDER BY rank ASC", statement)
        self.assertEqual(parameters, (RUN_ID,))

    @patch(
        "ai_editorial_team.infrastructure.persistence."
        "postgres_dashboard_repository.psycopg.connect"
    )
    def test_get_publications_filters_by_run(self, connect):
        _, cursor = _mock_connection(connect)
        expected = [
            {
                "platform": "instagram",
                "status": "published",
                "url": "https://instagram.com/p/example",
                "published_at": STARTED_AT,
            },
            {
                "platform": "x",
                "status": "failed",
                "url": None,
                "published_at": None,
            },
        ]
        cursor.fetchall.return_value = expected
        repository = PostgresDashboardRepository("postgresql://test")

        actual = repository.get_publications(RUN_ID)

        statement, parameters = cursor.execute.call_args.args
        self.assertIs(actual, expected)
        self.assertIn("FROM publications", statement)
        self.assertIn("WHERE run_id = %s", statement)
        self.assertIn("LOWER(platform)", statement)
        self.assertEqual(parameters, (RUN_ID,))

    @patch(
        "ai_editorial_team.infrastructure.persistence."
        "postgres_dashboard_repository.psycopg.connect"
    )
    def test_get_recent_runs_returns_platform_statuses_and_limits_results(
        self,
        connect,
    ):
        _, cursor = _mock_connection(connect)
        expected = [
            {
                "started_at": STARTED_AT,
                "status": "success",
                "duration_seconds": Decimal("12.5"),
                "instagram_status": "published",
                "x_status": "failed",
            }
        ]
        cursor.fetchall.return_value = expected
        repository = PostgresDashboardRepository("postgresql://test")

        actual = repository.get_recent_runs()

        statement, parameters = cursor.execute.call_args.args
        self.assertIs(actual, expected)
        self.assertIn("LEFT JOIN publications", statement)
        self.assertIn("AS instagram_status", statement)
        self.assertIn("AS x_status", statement)
        self.assertIn("ORDER BY r.started_at DESC", statement)
        self.assertIn("LIMIT %s", statement)
        self.assertEqual(parameters, (10,))

    @patch(
        "ai_editorial_team.infrastructure.persistence."
        "postgres_dashboard_repository.psycopg.connect"
    )
    def test_empty_results_are_returned_without_error(self, connect):
        _, cursor = _mock_connection(connect)
        cursor.fetchone.return_value = None
        cursor.fetchall.return_value = []
        repository = PostgresDashboardRepository("postgresql://test")

        self.assertIsNone(repository.get_latest_run())
        self.assertEqual(repository.get_stories(RUN_ID), [])
        self.assertEqual(repository.get_publications(RUN_ID), [])
        self.assertEqual(repository.get_recent_runs(), [])

    @patch(
        "ai_editorial_team.infrastructure.persistence."
        "postgres_dashboard_repository.psycopg.connect"
    )
    def test_database_errors_are_wrapped_without_connection_details(self, connect):
        connect.side_effect = psycopg.OperationalError(
            "connection to secret-user@secret-host failed"
        )
        repository = PostgresDashboardRepository("postgresql://secret")

        with self.assertRaises(PostgresDashboardRepositoryError) as context:
            repository.get_latest_run()

        self.assertEqual(
            str(context.exception),
            "Could not load dashboard data from PostgreSQL.",
        )
        self.assertNotIn("secret", str(context.exception))


def _mock_connection(connect):
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connect.return_value = connection
    return connection, cursor


if __name__ == "__main__":
    unittest.main()
