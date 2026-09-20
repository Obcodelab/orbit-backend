"""Import every module's models here so Base.metadata is fully populated
before Alembic autogenerates a migration — exists purely for the import
side effect. Add one line per module as it's built."""

from modules.auth import models as auth_models  # noqa: F401
