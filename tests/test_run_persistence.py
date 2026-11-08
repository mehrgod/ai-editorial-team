import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch
from uuid import UUID

import psycopg

from ai_editorial_team.application.run_tracking import RunTrackedEditorialWorkflow
from ai_editorial_team.infrastructure.persistence.postgres_run_repository import (
    PostgresRunRepository,
    PostgresRunRepositoryError,
)


RUN_ID = UUID("12345678-1234-5678-1234-567812345678")
STARTED_AT = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
PUBLISHED_AT = datetime(2026, 11, 7, 12, 0, 4, tzinfo=timezone.utc)
FINISHED_AT = datetime(2026, 11, 7, 12, 0, 5, tzinfo=timezone.utc)
STORY_IDS = [
    UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1"),
    UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2"),
    UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3"),
]
PUBLICATION_IDS = [
    UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1"),
    UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2"),
]
RANKED_STORIES = [
    {
        "rank": 1,
        "story": {
            "domain": "Sports",
            "headline": "Sports headline",
            "summary": "Sports summary",
            "reason": "Sports reason",
        },
        "editorial_reason": "Sports editorial reason",
    },
    {
        "rank": 2,
        "story": {
            "domain": "Artificial Intelligence",
            "headline": "AI headline",
            "summary": "AI summary",
            "reason": "AI reason",
        },
        "editorial_reason": "AI editorial reason",
    },
    {
        "rank": 3,
        "story": {
            "domain": "Finance",
            "headline": "Finance headline",
            "summary": "Finance summary",
            "reason": "Finance reason",
        },
        "editorial_reason": "Finance editorial reason",
    },
]
INSTAGRAM_PUBLICATION = {
    "platform": "Instagram",
    "publication_id": "instagram-123",
    "publication_url": "https://instagram.com/p/instagram-123",
}
X_PUBLICATION = {
    "platform": "X",
    "publication_id": "x-123",
    "publication_url": "https://x.com/i/web/status/x-123",
}
FAILED_X_PUBLICATION = {
    "platform": "X",
    "publication_id": "",
    "publication_url": "",
    "status": "failed",
    "error": "X is unavailable",
}
WORKFLOW_RESULT = {
    "instagram_story_contents": RANKED_STORIES,
    "instagram_publication": INSTAGRAM_PUBLICATION,
    "x_content": {"post": "Editorial post"},
    "x_publication": X_PUBLICATION,
}


class PostgresRunRepositoryTests(unittest.TestCase):
    @patch(
        "ai_editorial_team.infrastructure.persistence."
        "postgres_run_repository.psycopg.connect"
    )
    def test_create_run_inserts_running_and_commits(self, connect):
        connection = _mock_connection(connect)
        repository = PostgresRunRepository("postgresql://test")

        repository.create_run(RUN_ID, STARTED_AT)

        cursor = connection.cursor.return_value.__enter__.return_value
        statement, parameters = cursor.execute.call_args.args
        self.assertIn("INSERT INTO runs", statement)
        self.assertIn("id, started_at, status", statement)
        self.assertEqual(parameters, (RUN_ID, STARTED_AT, "running"))
        self.assertEqual(cursor.execute.call_args.kwargs, {"prepare": False})
        connect.assert_called_once_with(
            "postgresql://test",
            prepare_threshold=None,
        )
        connection.commit.assert_called_once_with()
        connection.close.assert_called_once_with()

    @patch(
        "ai_editorial_team.infrastructure.persistence."
        "postgres_run_repository.psycopg.connect"
    )
    def test_finish_run_updates_status_duration_and_commits(self, connect):
        connection = _mock_connection(connect)
        repository = PostgresRunRepository("postgresql://test")

        repository.finish_run(RUN_ID, FINISHED_AT, "success", 5.25)

        cursor = connection.cursor.return_value.__enter__.return_value
        statement, parameters = cursor.execute.call_args.args
        self.assertIn("UPDATE runs", statement)
        self.assertIn("duration_seconds", statement)
        self.assertEqual(parameters, (FINISHED_AT, "success", 5.25, RUN_ID))
        connection.commit.assert_called_once_with()
        connection.close.assert_called_once_with()

    @patch(
        "ai_editorial_team.infrastructure.persistence."
        "postgres_run_repository.psycopg.connect"
    )
    def test_save_stories_inserts_three_mapped_rows_with_generated_ids(self, connect):
        connection = _mock_connection(connect)
        uuid_factory = Mock(side_effect=STORY_IDS)
        repository = PostgresRunRepository(
            "postgresql://test",
            uuid_factory=uuid_factory,
        )

        repository.save_stories(RUN_ID, RANKED_STORIES)

        cursor = connection.cursor.return_value.__enter__.return_value
        statement, parameters = _executed_batch(cursor)
        self.assertIn("INSERT INTO stories", statement)
        self.assertIn("WHERE NOT EXISTS", statement)
        self.assertIn("WHERE run_id = %s AND rank = %s", statement)
        self.assertEqual(len(parameters), 3)
        self.assertEqual(
            parameters,
            [
                (
                    STORY_IDS[0],
                    RUN_ID,
                    1,
                    "Sports",
                    "Sports headline",
                    "Sports summary",
                    "Sports editorial reason",
                    RUN_ID,
                    1,
                ),
                (
                    STORY_IDS[1],
                    RUN_ID,
                    2,
                    "Artificial Intelligence",
                    "AI headline",
                    "AI summary",
                    "AI editorial reason",
                    RUN_ID,
                    2,
                ),
                (
                    STORY_IDS[2],
                    RUN_ID,
                    3,
                    "Finance",
                    "Finance headline",
                    "Finance summary",
                    "Finance editorial reason",
                    RUN_ID,
                    3,
                ),
            ],
        )
        self.assertEqual(uuid_factory.call_count, 3)
        connect.assert_called_once_with(
            "postgresql://test",
            prepare_threshold=None,
        )
        connection.commit.assert_called_once_with()
        connection.close.assert_called_once_with()

    @patch(
        "ai_editorial_team.infrastructure.persistence."
        "postgres_run_repository.psycopg.connect"
    )
    def test_save_stories_surfaces_database_errors(self, connect):
        connect.side_effect = psycopg.OperationalError("database unavailable")
        repository = PostgresRunRepository("postgresql://test")

        with self.assertRaises(PostgresRunRepositoryError) as context:
            repository.save_stories(RUN_ID, RANKED_STORIES)

        self.assertIn("persist ranked stories", str(context.exception))

    @patch(
        "ai_editorial_team.infrastructure.persistence."
        "postgres_run_repository.psycopg.connect"
    )
    def test_save_publications_maps_instagram_and_x_successes(self, connect):
        connection = _mock_connection(connect)
        uuid_factory = Mock(side_effect=PUBLICATION_IDS)
        repository = PostgresRunRepository(
            "postgresql://test",
            uuid_factory=uuid_factory,
        )

        repository.save_publications(
            RUN_ID,
            [INSTAGRAM_PUBLICATION, X_PUBLICATION],
            PUBLISHED_AT,
        )

        cursor = connection.cursor.return_value.__enter__.return_value
        statement, parameters = _executed_batch(cursor)
        self.assertIn("INSERT INTO publications", statement)
        self.assertEqual(
            parameters,
            [
                (
                    PUBLICATION_IDS[0],
                    RUN_ID,
                    "instagram",
                    "published",
                    "https://instagram.com/p/instagram-123",
                    PUBLISHED_AT,
                    RUN_ID,
                    "instagram",
                ),
                (
                    PUBLICATION_IDS[1],
                    RUN_ID,
                    "x",
                    "published",
                    "https://x.com/i/web/status/x-123",
                    PUBLISHED_AT,
                    RUN_ID,
                    "x",
                ),
            ],
        )
        self.assertEqual(uuid_factory.call_count, 2)
        connection.commit.assert_called_once_with()
        connection.close.assert_called_once_with()

    @patch(
        "ai_editorial_team.infrastructure.persistence."
        "postgres_run_repository.psycopg.connect"
    )
    def test_save_publications_maps_failure_to_null_url_and_timestamp(self, connect):
        connection = _mock_connection(connect)
        repository = PostgresRunRepository(
            "postgresql://test",
            uuid_factory=lambda: PUBLICATION_IDS[1],
        )

        repository.save_publications(RUN_ID, [FAILED_X_PUBLICATION], PUBLISHED_AT)

        cursor = connection.cursor.return_value.__enter__.return_value
        _, parameters = _executed_batch(cursor)
        self.assertEqual(
            parameters,
            [
                (
                    PUBLICATION_IDS[1],
                    RUN_ID,
                    "x",
                    "failed",
                    None,
                    None,
                    RUN_ID,
                    "x",
                )
            ],
        )

    @patch(
        "ai_editorial_team.infrastructure.persistence."
        "postgres_run_repository.psycopg.connect"
    )
    def test_save_publications_uses_run_and_platform_duplicate_guard(self, connect):
        connection = _mock_connection(connect)
        repository = PostgresRunRepository(
            "postgresql://test",
            uuid_factory=lambda: PUBLICATION_IDS[0],
        )

        repository.save_publications(RUN_ID, [INSTAGRAM_PUBLICATION], PUBLISHED_AT)

        cursor = connection.cursor.return_value.__enter__.return_value
        statement, _ = _executed_batch(cursor)
        self.assertIn("WHERE NOT EXISTS", statement)
        self.assertIn("WHERE run_id = %s AND platform = %s", statement)

    @patch(
        "ai_editorial_team.infrastructure.persistence."
        "postgres_run_repository.psycopg.connect"
    )
    def test_save_publications_surfaces_database_errors(self, connect):
        connect.side_effect = psycopg.OperationalError("database unavailable")
        repository = PostgresRunRepository("postgresql://test")

        with self.assertRaises(PostgresRunRepositoryError) as context:
            repository.save_publications(
                RUN_ID,
                [INSTAGRAM_PUBLICATION, X_PUBLICATION],
                PUBLISHED_AT,
            )

        self.assertIn("persist publication results", str(context.exception))


class RunTrackedEditorialWorkflowTests(unittest.TestCase):
    def test_run_creation_failure_surfaces_before_workflow_starts(self):
        workflow = Mock()
        repository = Mock()
        database_error = RuntimeError("database unavailable")
        repository.create_run.side_effect = database_error
        tracker = RunTrackedEditorialWorkflow(
            workflow=workflow,
            run_repository=repository,
            uuid_factory=lambda: RUN_ID,
            now_factory=lambda: STARTED_AT,
            timer=lambda: 10.0,
        )

        with self.assertRaises(RuntimeError) as context:
            tracker.run()

        self.assertIs(context.exception, database_error)
        workflow.run.assert_not_called()
        repository.finish_run.assert_not_called()

    def test_successful_workflow_marks_run_success(self):
        workflow = Mock()
        workflow.run.return_value = WORKFLOW_RESULT
        repository = Mock()
        tracker = RunTrackedEditorialWorkflow(
            workflow=workflow,
            run_repository=repository,
            uuid_factory=lambda: RUN_ID,
            now_factory=Mock(side_effect=[STARTED_AT, PUBLISHED_AT, FINISHED_AT]),
            timer=Mock(side_effect=[10.0, 15.25]),
        )

        actual = tracker.run()

        self.assertIs(actual, WORKFLOW_RESULT)
        repository.create_run.assert_called_once_with(RUN_ID, STARTED_AT)
        repository.save_stories.assert_called_once_with(RUN_ID, RANKED_STORIES)
        repository.save_publications.assert_called_once_with(
            RUN_ID,
            [INSTAGRAM_PUBLICATION, X_PUBLICATION],
            PUBLISHED_AT,
        )
        repository.finish_run.assert_called_once_with(
            RUN_ID,
            FINISHED_AT,
            "success",
            5.25,
        )

    def test_partial_publication_failure_is_passed_to_persistence(self):
        partial_result = {
            **WORKFLOW_RESULT,
            "x_publication": FAILED_X_PUBLICATION,
        }
        workflow = Mock()
        workflow.run.return_value = partial_result
        repository = Mock()
        tracker = RunTrackedEditorialWorkflow(
            workflow=workflow,
            run_repository=repository,
            uuid_factory=lambda: RUN_ID,
            now_factory=Mock(side_effect=[STARTED_AT, PUBLISHED_AT, FINISHED_AT]),
            timer=Mock(side_effect=[10.0, 15.25]),
        )

        tracker.run()

        repository.save_publications.assert_called_once_with(
            RUN_ID,
            [INSTAGRAM_PUBLICATION, FAILED_X_PUBLICATION],
            PUBLISHED_AT,
        )
        repository.finish_run.assert_called_once_with(
            RUN_ID,
            FINISHED_AT,
            "success",
            5.25,
        )

    def test_failed_workflow_marks_run_failed_and_reraises_original_exception(self):
        original_error = RuntimeError("workflow failed")
        workflow = Mock()
        workflow.run.side_effect = original_error
        repository = Mock()
        tracker = RunTrackedEditorialWorkflow(
            workflow=workflow,
            run_repository=repository,
            uuid_factory=lambda: RUN_ID,
            now_factory=Mock(side_effect=[STARTED_AT, FINISHED_AT]),
            timer=Mock(side_effect=[20.0, 22.5]),
        )

        with self.assertRaises(RuntimeError) as context:
            tracker.run()

        self.assertIs(context.exception, original_error)
        repository.create_run.assert_called_once_with(RUN_ID, STARTED_AT)
        repository.save_stories.assert_not_called()
        repository.save_publications.assert_not_called()
        repository.finish_run.assert_called_once_with(
            RUN_ID,
            FINISHED_AT,
            "failed",
            2.5,
        )

    def test_failed_status_update_does_not_mask_workflow_exception(self):
        original_error = RuntimeError("workflow failed")
        workflow = Mock()
        workflow.run.side_effect = original_error
        repository = Mock()
        repository.finish_run.side_effect = RuntimeError("database unavailable")
        tracker = RunTrackedEditorialWorkflow(
            workflow=workflow,
            run_repository=repository,
            uuid_factory=lambda: RUN_ID,
            now_factory=Mock(side_effect=[STARTED_AT, FINISHED_AT]),
            timer=Mock(side_effect=[30.0, 31.0]),
        )

        with self.assertRaises(RuntimeError) as context:
            tracker.run()

        self.assertIs(context.exception, original_error)

    def test_story_persistence_failure_is_surfaced_and_marks_run_failed(self):
        database_error = PostgresRunRepositoryError("story insert failed")
        workflow = Mock()
        workflow.run.return_value = WORKFLOW_RESULT
        repository = Mock()
        repository.save_stories.side_effect = database_error
        tracker = RunTrackedEditorialWorkflow(
            workflow=workflow,
            run_repository=repository,
            uuid_factory=lambda: RUN_ID,
            now_factory=Mock(side_effect=[STARTED_AT, FINISHED_AT]),
            timer=Mock(side_effect=[40.0, 41.5]),
        )

        with self.assertRaises(PostgresRunRepositoryError) as context:
            tracker.run()

        self.assertIs(context.exception, database_error)
        repository.save_stories.assert_called_once_with(RUN_ID, RANKED_STORIES)
        repository.save_publications.assert_not_called()
        repository.finish_run.assert_called_once_with(
            RUN_ID,
            FINISHED_AT,
            "failed",
            1.5,
        )

    def test_publication_persistence_failure_is_surfaced_and_marks_run_failed(self):
        database_error = PostgresRunRepositoryError("publication insert failed")
        workflow = Mock()
        workflow.run.return_value = WORKFLOW_RESULT
        repository = Mock()
        repository.save_publications.side_effect = database_error
        tracker = RunTrackedEditorialWorkflow(
            workflow=workflow,
            run_repository=repository,
            uuid_factory=lambda: RUN_ID,
            now_factory=Mock(side_effect=[STARTED_AT, PUBLISHED_AT, FINISHED_AT]),
            timer=Mock(side_effect=[50.0, 52.0]),
        )

        with self.assertRaises(PostgresRunRepositoryError) as context:
            tracker.run()

        self.assertIs(context.exception, database_error)
        repository.save_stories.assert_called_once_with(RUN_ID, RANKED_STORIES)
        repository.save_publications.assert_called_once_with(
            RUN_ID,
            [INSTAGRAM_PUBLICATION, X_PUBLICATION],
            PUBLISHED_AT,
        )
        repository.finish_run.assert_called_once_with(
            RUN_ID,
            FINISHED_AT,
            "failed",
            2.0,
        )


def _mock_connection(connect):
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connect.return_value = connection
    return connection


def _executed_batch(cursor):
    calls = cursor.execute.call_args_list
    statements = [call.args[0] for call in calls]
    parameters = [call.args[1] for call in calls]
    if statements:
        assert all(statement == statements[0] for statement in statements)
    assert all(call.kwargs == {"prepare": False} for call in calls)
    return statements[0], parameters


if __name__ == "__main__":
    unittest.main()
