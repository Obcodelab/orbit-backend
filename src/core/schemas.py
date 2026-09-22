from pydantic import ConfigDict

# populate_by_name lets a response be built with its real field name
# (e.g. org_id=...) as well as the ORM-matching alias (id=...) used when
# validating straight from a SQLAlchemy object.
FROM_ORM = ConfigDict(from_attributes=True, populate_by_name=True)
