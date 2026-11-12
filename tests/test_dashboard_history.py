import unittest
from datetime import datetime, time, timezone
from pathlib import Path
from unittest.mock import Mock, call, patch
from uuid import UUID

from streamlit.testing.v1 import AppTest

from ai_editorial_team.infrastructure.aws.dashboard_control import ScheduleDetails


DASHBOARD_PATH = Path(__file__).resolve().parents[1] / "dashboard.py"
LATEST_RUN_ID = UUID("11111111-1111-1111-1111-111111111111")
MORNING_RUN_ID = UUID("22222222-2222-2222-2222-222222222222")
EVENING_RUN_ID = UUID("33333333-3333-3333-3333-333333333333")


class DashboardHistoryTests(unittest.TestCase):
    def test_selecting_second_run_loads_its_stories_and_publications(self):
        latest_run = _run(LATEST_RUN_ID, hour=18)
        morning_run = _run(MORNING_RUN_ID, hour=13)
        evening_run = _run(EVENING_RUN_ID, hour=23)
        repository = Mock()
        repository.get_latest_run.return_value = latest_run
        repository.get_runs_for_date.return_value = [morning_run, evening_run]
        repository.get_recent_runs.return_value = []
        repository.get_stories.side_effect = lambda run_id: [
            {
                "rank": 1,
                "domain": "Technology",
                "headline": f"Headline for {run_id}",
                "summary": "Summary",
                "editorial_reason": "Reason",
            }
        ]
        repository.get_publications.side_effect = lambda run_id: [
            {
                "platform": "instagram",
                "status": "published",
                "url": f"https://example.com/{run_id}",
                "published_at": latest_run["started_at"],
            }
        ]
        control = Mock()
        control.get_schedule.return_value = ScheduleDetails(
            expression="cron(0 18 * * ? *)",
            timezone="America/New_York",
            posting_time=time(18),
            state="ENABLED",
        )

        with patch(
            "ai_editorial_team.infrastructure.persistence."
            "postgres_dashboard_repository.PostgresDashboardRepository.from_env",
            return_value=repository,
        ), patch(
            "ai_editorial_team.infrastructure.aws."
            "dashboard_control.AwsDashboardControl.from_default_credentials",
            return_value=control,
        ):
            app = AppTest.from_file(str(DASHBOARD_PATH)).run(timeout=10)
            app.selectbox(key="previous_posts_run").set_value(1).run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(
            repository.get_stories.call_args_list[-1], call(EVENING_RUN_ID)
        )
        self.assertEqual(
            repository.get_publications.call_args_list[-1],
            call(EVENING_RUN_ID),
        )
        self.assertIn(
            f"Headline for {EVENING_RUN_ID}",
            [subheader.value for subheader in app.subheader],
        )


def _run(run_id: UUID, *, hour: int):
    return {
        "id": run_id,
        "started_at": datetime(2026, 11, 10, hour, tzinfo=timezone.utc),
        "finished_at": datetime(2026, 11, 10, hour, 5, tzinfo=timezone.utc),
        "status": "success",
        "duration_seconds": 300,
    }


if __name__ == "__main__":
    unittest.main()
