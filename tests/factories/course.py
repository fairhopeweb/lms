import factory
from factory.alchemy import SQLAlchemyModelFactory

from lms.models import LegacyCourse
from tests.factories import ApplicationInstance

LegacyCourse = factory.make_factory(
    LegacyCourse,
    FACTORY_CLASS=SQLAlchemyModelFactory,
    application_instance=factory.SubFactory(ApplicationInstance),
    authority_provided_id=factory.Faker("hexify", text="^" * 40),
)
