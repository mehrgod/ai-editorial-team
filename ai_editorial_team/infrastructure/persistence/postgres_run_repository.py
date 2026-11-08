from dataclasses import dataclass
from datetime import datetime
import os
from typing import Callable
from uuid import UUID, uuid4

from dotenv import load_dotenv
import psycopg

from ai_editorial_team.domain.models import PublicationResult, RankedStory
from ai_editorial_team.domain.ports import RunRepository


class PostgresRunRepositoryError(RuntimeError):
    """Raised when workflow persistence fails."""


class PostgresRunRepositoryConfigurationError(PostgresRunRepositoryError):
    """Raised when PostgreSQL persistence configuration is missing."""


@dataclass(frozen=True)
class PostgresRunRepository(RunRepository):
    """Persists workflow execution data in PostgreSQL."""

    database_url: str
    uuid_factory: Callable[[], UUID] = uuid4

    @classmethod
    def from_env(cls) -> "PostgresRunRepository":
        load_dotenv()
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise PostgresRunRepositoryConfigurationError(
                "DATABASE_URL is not set. Set it before running the application."
            )
        return cls(database_url=database_url)

    def create_run(self, run_id: UUID, started_at: datetime) -> None:
        self._execute(
            """
            INSERT INTO runs (id, started_at, status)
            VALUES (%s, %s, %s)
            """,
            (run_id, started_at, "running"),
            operation="create workflow run",
        )

    def finish_run(
        self,
        run_id: UUID,
        finished_at: datetime,
        status: str,
        duration_seconds: float,
    ) -> None:
        self._execute(
            """
            UPDATE runs
            SET finished_at = %s, status = %s, duration_seconds = %s
            WHERE id = %s
            """,
            (finished_at, status, duration_seconds, run_id),
            operation=f"mark workflow run as {status}",
        )

    def save_stories(self, run_id: UUID, stories: list[RankedStory]) -> None:
        parameters = [
            (
                self.uuid_factory(),
                run_id,
                ranked_story["rank"],
                ranked_story["story"]["domain"],
                ranked_story["story"]["headline"],
                ranked_story["story"]["summary"],
                ranked_story["editorial_reason"],
                run_id,
                ranked_story["rank"],
            )
            for ranked_story in stories
        ]

        self._execute_many(
            """
            INSERT INTO stories (
                id,
                run_id,
                rank,
                domain,
                headline,
                summary,
                editorial_reason
            )
            SELECT %s, %s, %s, %s, %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1
                FROM stories
                WHERE run_id = %s AND rank = %s
            )
            """,
            parameters,
            operation="persist ranked stories",
        )

    def save_publications(
        self,
        run_id: UUID,
        publications: list[PublicationResult],
        published_at: datetime,
    ) -> None:
        parameters = []
        for publication in publications:
            platform = publication["platform"].strip().lower()
            failed = publication.get("status") == "failed"
            parameters.append(
                (
                    self.uuid_factory(),
                    run_id,
                    platform,
                    "failed" if failed else "published",
                    None if failed else publication["publication_url"],
                    None if failed else published_at,
                    run_id,
                    platform,
                )
            )

        self._execute_many(
            """
            INSERT INTO publications (
                id,
                run_id,
                platform,
                status,
                url,
                published_at
            )
            SELECT %s, %s, %s, %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1
                FROM publications
                WHERE run_id = %s AND platform = %s
            )
            """,
            parameters,
            operation="persist publication results",
        )

    def _execute(self, statement: str, parameters: tuple, *, operation: str) -> None:
        connection = None
        try:
            connection = psycopg.connect(
                self.database_url,
                prepare_threshold=None,
            )
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters, prepare=False)
            connection.commit()
        except psycopg.Error as exc:
            raise PostgresRunRepositoryError(
                f"PostgreSQL could not {operation}: {exc}"
            ) from exc
        finally:
            if connection is not None:
                connection.close()

    def _execute_many(
        self, statement: str, parameters: list[tuple], *, operation: str
    ) -> None:
        connection = None
        try:
            connection = psycopg.connect(
                self.database_url,
                prepare_threshold=None,
            )
            with connection.cursor() as cursor:
                for parameter_set in parameters:
                    cursor.execute(statement, parameter_set, prepare=False)
            connection.commit()
        except psycopg.Error as exc:
            raise PostgresRunRepositoryError(
                f"PostgreSQL could not {operation}: {exc}"
            ) from exc
        finally:
            if connection is not None:
                connection.close()
