import os
from typing import Any
from uuid import UUID

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row


class PostgresDashboardRepositoryError(RuntimeError):
    """Raised when dashboard data cannot be loaded from PostgreSQL."""


class PostgresDashboardRepositoryConfigurationError(
    PostgresDashboardRepositoryError
):
    """Raised when dashboard database configuration is missing."""


class PostgresDashboardRepository:
    """Provides read-only dashboard queries for editorial workflow data."""

    def __init__(self, database_url: str):
        self.database_url = database_url

    @classmethod
    def from_env(cls) -> "PostgresDashboardRepository":
        load_dotenv(".env")
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise PostgresDashboardRepositoryConfigurationError(
                "DATABASE_URL is not set. Add it to the local .env file."
            )
        return cls(database_url)

    def get_latest_run(self) -> dict[str, Any] | None:
        return self._fetch_one(
            """
            SELECT id, started_at, finished_at, status, duration_seconds
            FROM runs
            ORDER BY started_at DESC NULLS LAST
            LIMIT 1
            """
        )

    def get_stories(self, run_id: UUID) -> list[dict[str, Any]]:
        return self._fetch_all(
            """
            SELECT rank, domain, headline, summary, editorial_reason
            FROM stories
            WHERE run_id = %s
            ORDER BY rank ASC
            """,
            (run_id,),
        )

    def get_publications(self, run_id: UUID) -> list[dict[str, Any]]:
        return self._fetch_all(
            """
            SELECT platform, status, url, published_at
            FROM publications
            WHERE run_id = %s
            ORDER BY CASE LOWER(platform)
                WHEN 'instagram' THEN 1
                WHEN 'x' THEN 2
                ELSE 3
            END
            """,
            (run_id,),
        )

    def get_recent_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._fetch_all(
            """
            SELECT
                r.started_at,
                r.status,
                r.duration_seconds,
                MAX(
                    CASE WHEN LOWER(p.platform) = 'instagram' THEN p.status END
                ) AS instagram_status,
                MAX(
                    CASE WHEN LOWER(p.platform) = 'x' THEN p.status END
                ) AS x_status
            FROM runs AS r
            LEFT JOIN publications AS p ON p.run_id = r.id
            GROUP BY r.id, r.started_at, r.status, r.duration_seconds
            ORDER BY r.started_at DESC NULLS LAST
            LIMIT %s
            """,
            (limit,),
        )

    def _fetch_one(
        self,
        statement: str,
        parameters: tuple | None = None,
    ) -> dict[str, Any] | None:
        rows = self._query(statement, parameters, fetch_one=True)
        return rows

    def _fetch_all(
        self,
        statement: str,
        parameters: tuple | None = None,
    ) -> list[dict[str, Any]]:
        rows = self._query(statement, parameters, fetch_one=False)
        return rows

    def _query(
        self,
        statement: str,
        parameters: tuple | None,
        *,
        fetch_one: bool,
    ):
        connection = None
        try:
            connection = psycopg.connect(
                self.database_url,
                prepare_threshold=None,
                row_factory=dict_row,
            )
            with connection.cursor() as cursor:
                if parameters is None:
                    cursor.execute(statement, prepare=False)
                else:
                    cursor.execute(statement, parameters, prepare=False)
                if fetch_one:
                    return cursor.fetchone()
                return cursor.fetchall()
        except psycopg.Error as exc:
            raise PostgresDashboardRepositoryError(
                "Could not load dashboard data from PostgreSQL."
            ) from exc
        finally:
            if connection is not None:
                connection.close()
