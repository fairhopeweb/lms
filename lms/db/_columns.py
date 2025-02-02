import sqlalchemy as sa


def varchar_enum(enum, max_length=64, nullable=False, unique=False):
    """Return a SA column type to store the python enum.Enum as a varchar in a table."""
    return sa.Column(
        sa.Enum(
            enum,
            # In order to maintain maximum flexibility we will only enforce the
            # type on the Python side, and leave the Postgres side open as a plain
            # VARCHAR
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            # Without a length SQLAlchemy will constrain it to the longest value
            # we happen to have right now, which could limit us in future
            length=max_length,
            # Use the string values, not the keys to persist the values
            values_callable=lambda obj: [item.value for item in obj],
        ),
        nullable=nullable,
        unique=unique,
    )
