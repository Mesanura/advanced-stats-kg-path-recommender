from contextlib import closing
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import get_settings


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def alembic_config(database: Path, monkeypatch) -> Config:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database.as_posix()}")
    get_settings.cache_clear()
    return Config(str(BACKEND_ROOT / "alembic.ini"))


def test_fresh_database_upgrades_to_staged_schema(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "fresh.db"
    command.upgrade(alembic_config(database, monkeypatch), "head")

    with closing(sqlite3.connect(database)) as connection:
        columns = {
            row[1]: row for row in connection.execute("PRAGMA table_info(learning_path_items)")
        }
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert columns["stage"][3] == 1
    assert revision == ("0002",)
    get_settings.cache_clear()


def test_existing_database_backfills_stage_and_stales_paths(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "existing.db"
    config = alembic_config(database, monkeypatch)
    command.upgrade(config, "0001")
    with closing(sqlite3.connect(database)) as connection:
        connection.executescript(
            """
            INSERT INTO grades (id, name) VALUES (1, '2026级');
            INSERT INTO classrooms (id, grade_id, name) VALUES (1, 1, '高级统计01班');
            INSERT INTO users (id, username, password_hash, display_name, role, is_active)
            VALUES (1, '20260001', 'hash', '学生01', 'STUDENT', 1);
            INSERT INTO student_profiles (id, user_id, student_no, classroom_id)
            VALUES (1, 1, '20260001', 1);
            INSERT INTO knowledge_points
              (id, code, name, chapter, dimension, difficulty, resource_url, is_active)
            VALUES
              (1, 'descriptive_statistics', '描述性统计', '第一章', 'STATISTICS_FOUNDATION', 1, 'https://example.com', 1);
            INSERT INTO learning_paths
              (id, student_id, target_knowledge_point_id, algorithm, state, score, config_snapshot)
            VALUES (1, 1, 1, 'BKT', 'CURRENT', 0.5, '{}');
            INSERT INTO learning_path_items
              (path_id, sequence, knowledge_point_id, status, mastery_score)
            VALUES (1, 1, 1, 'TARGET', 0.2);
            """
        )
    command.upgrade(config, "head")

    with closing(sqlite3.connect(database)) as connection:
        stage = connection.execute(
            "SELECT stage FROM learning_path_items WHERE path_id = 1"
        ).fetchone()
        state = connection.execute(
            "SELECT state FROM learning_paths WHERE id = 1"
        ).fetchone()
    assert stage == (1,)
    assert state == ("STALE",)
    get_settings.cache_clear()
