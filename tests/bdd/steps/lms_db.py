"""Insert LMS specific objects into the DB."""

import sqlalchemy
from behave import step  # pylint:disable=no-name-in-module
from sqlalchemy.orm import sessionmaker

from lms import db, models
from tests.bdd.step_context import StepContext
from tests.conftest import get_test_database_url

TEST_DATABASE_URL = get_test_database_url(
    default="postgresql://postgres@localhost:5433/lms_bddtests"
)


class LMSDBContext(StepContext):
    context_key = "db"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.engine = sqlalchemy.create_engine(TEST_DATABASE_URL)
        self.session_maker = sessionmaker(bind=self.engine.connect())
        db.init(self.engine, stamp=False, drop=True)

        self.session = None
        self.modified_tables = None

    def create_row(self, model_class, data):
        model_class = getattr(models, model_class)
        model = model_class(**data)
        self.session.add(model)
        self.session.commit()

        self.modified_tables.append(model_class.__table__)

    def wipe(self, tables):
        if not tables:
            return

        table_names = ", ".join(f'"{table.name}"' for table in tables)
        self.session.execute(f"TRUNCATE {table_names} CASCADE;")
        self.session.commit()

    def do_setup(self):
        self.session = self.session_maker()
        self.modified_tables = []

    def do_teardown(self):
        self.wipe(self.modified_tables)
        self.session.close()


@step("I create an LMS DB '{model_class}'")
def create_row_from_fixture(context, model_class):
    context.db.create_row(model_class, data={row[0]: row[1] for row in context.table})
