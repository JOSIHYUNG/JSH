import atexit
import os
import shutil
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config


BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(tempfile.mkdtemp(prefix="jsh-backend-tests-"))
TEST_DATABASE = TEST_ROOT / "test.db"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE.as_posix()}"
os.environ["STORAGE_ROOT"] = str(TEST_ROOT / "storage")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENAI_VECTOR_STORE_ID"] = ""

alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
alembic_config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
command.upgrade(alembic_config, "head")

atexit.register(shutil.rmtree, TEST_ROOT, True)
