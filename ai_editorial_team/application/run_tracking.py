from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from time import perf_counter
from typing import Callable, Protocol
from uuid import UUID, uuid4

from ai_editorial_team.domain.models import EditorialPackage, RankedStory
from ai_editorial_team.domain.ports import RunRepository


logger = logging.getLogger(__name__)


class EditorialWorkflowRunner(Protocol):
    """Interface for executing an editorial workflow."""

    def run(self) -> EditorialPackage:
        ...


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RunTrackedEditorialWorkflow:
    """Records the lifecycle of one delegated editorial workflow execution."""

    workflow: EditorialWorkflowRunner
    run_repository: RunRepository
    uuid_factory: Callable[[], UUID] = uuid4
    now_factory: Callable[[], datetime] = _utc_now
    timer: Callable[[], float] = perf_counter

    def run(self) -> EditorialPackage:
        run_id = self.uuid_factory()
        started_at = self.now_factory()
        started_timer = self.timer()

        self.run_repository.create_run(run_id, started_at)

        try:
            result = self.workflow.run()
            ranked_stories: list[RankedStory] = [
                {
                    "rank": story_content["rank"],
                    "story": story_content["story"],
                    "editorial_reason": story_content["editorial_reason"],
                }
                for story_content in result["instagram_story_contents"]
            ]
            self.run_repository.save_stories(run_id, ranked_stories)
            self.run_repository.save_publications(
                run_id,
                [result["instagram_publication"], result["x_publication"]],
                self.now_factory(),
            )
        except Exception:
            finished_at = self.now_factory()
            duration_seconds = self.timer() - started_timer
            try:
                self.run_repository.finish_run(
                    run_id,
                    finished_at,
                    "failed",
                    duration_seconds,
                )
            except Exception:
                logger.exception("Could not mark workflow run %s as failed.", run_id)
            raise

        finished_at = self.now_factory()
        duration_seconds = self.timer() - started_timer
        self.run_repository.finish_run(
            run_id,
            finished_at,
            "success",
            duration_seconds,
        )
        return result
