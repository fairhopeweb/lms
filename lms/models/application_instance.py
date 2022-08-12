import logging
from datetime import datetime
from urllib.parse import urlparse

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from lms.db import BASE
from lms.models.application_settings import ApplicationSettings
from lms.models.exceptions import ReusedConsumerKey

LOG = logging.getLogger(__name__)


class ApplicationInstance(BASE):
    """Class to represent a single lms install."""

    __tablename__ = "application_instances"
    __table_args__ = (
        # For LTI1.3 instances we allow consumer_key to be null as long as we have a registration and deployment_id.
        # Note that when consumer_key is present we don't require lti_registration_id and deployment_id to be null
        # it could be an instance that has been upgraded from LTI1.1 to LTI1.3 having values for all three fields.
        sa.CheckConstraint(
            """(consumer_key IS NULL AND lti_registration_id IS NOT NULL and deployment_id IS NOT NULL)
            OR (consumer_key IS NOT NULL)""",
            name="consumer_key_required_for_lti_11",
        ),
        # For LTI 1.3, registration and deployment_id uniquely identify the instance.
        sa.UniqueConstraint("lti_registration_id", "deployment_id"),
    )

    id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

    organization_id = sa.Column(
        sa.Integer(), sa.ForeignKey("organization.id"), nullable=True
    )
    organization = sa.orm.relationship("Organization")
    """The organization this application instance belongs to."""

    consumer_key = sa.Column(sa.Unicode, unique=True, nullable=True)
    shared_secret = sa.Column(sa.Unicode, nullable=False)
    lms_url = sa.Column(sa.Unicode(2048), nullable=False)
    requesters_email = sa.Column(sa.Unicode(2048), nullable=False)

    created = sa.Column(sa.TIMESTAMP, default=datetime.utcnow(), nullable=False)

    developer_key = sa.Column(sa.Unicode)
    developer_secret = sa.Column(sa.LargeBinary)
    aes_cipher_iv = sa.Column(sa.LargeBinary)
    provisioning = sa.Column(
        sa.Boolean(),
        default=True,
        server_default=sa.sql.expression.true(),
        nullable=False,
    )

    settings = sa.Column(
        "settings",
        ApplicationSettings.as_mutable(JSONB),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )

    #: A unique identifier for the LMS instance.
    tool_consumer_instance_guid = sa.Column(sa.UnicodeText, nullable=True)

    #: The LMS product name, e.g. "canvas" or "moodle".
    tool_consumer_info_product_family_code = sa.Column(sa.UnicodeText, nullable=True)

    #: A plain text description of the LMS instance, e.g. "University of Hypothesis"
    tool_consumer_instance_description = sa.Column(sa.UnicodeText, nullable=True)

    #: The URL of the LMS instance, e.g. "https://hypothesis.instructure.com".
    tool_consumer_instance_url = sa.Column(sa.UnicodeText, nullable=True)

    #: The name of the LMS instance, e.g. "HypothesisU".
    tool_consumer_instance_name = sa.Column(sa.UnicodeText, nullable=True)

    #: An contact email, e.g. "System.Admin@school.edu"
    tool_consumer_instance_contact_email = sa.Column(sa.UnicodeText, nullable=True)

    #: Version of the LMS, e.g. "9.1.7081"
    tool_consumer_info_version = sa.Column(sa.UnicodeText, nullable=True)

    #: This Canvas custom variable substitution $Canvas.api.domain.
    #: We request this in our config.xml file and name it "custom_canvas_api_domain":
    #:
    #: https://github.com/hypothesis/lms/blob/5394cf2bfb92cb219e177f3c0a7991add024f242/lms/templates/config.xml.jinja2#L20
    #:
    #: See https://canvas.instructure.com/doc/api/file.tools_variable_substitutions.html
    custom_canvas_api_domain = sa.Column(sa.UnicodeText, nullable=True)

    #: A list of all the OAuth2Tokens for this application instance
    #: (each token belongs to a different user of this application
    #: instance's LMS).
    access_tokens = sa.orm.relationship(
        "OAuth2Token",
        back_populates="application_instance",
        foreign_keys="OAuth2Token.application_instance_id",
    )

    #: A list of all the courses for this application instance.
    courses = sa.orm.relationship("LegacyCourse", back_populates="application_instance")

    #: A list of all the GroupInfo's for this application instance.
    group_infos = sa.orm.relationship(
        "GroupInfo",
        back_populates="application_instance",
        foreign_keys="GroupInfo.application_instance_id",
    )

    #: A list of all the files for this application instance.
    files = sa.orm.relationship("File", back_populates="application_instance")

    #: LTIRegistration this instance belong to.
    lti_registration_id = sa.Column(
        sa.Integer(),
        sa.ForeignKey("lti_registration.id", ondelete="cascade"),
        nullable=True,
    )

    lti_registration = sa.orm.relationship(
        "LTIRegistration", back_populates="application_instances"
    )

    #: Unique identifier of this instance per LTIRegistration
    deployment_id = sa.Column(sa.UnicodeText, nullable=True)

    def decrypted_developer_secret(self, aes_service):
        if self.developer_secret is None:
            return None

        return aes_service.decrypt(self.aes_cipher_iv, self.developer_secret)

    def lms_host(self):
        """
        Return the hostname part of this ApplicationInstance's lms_url.

        For example if application_instance.lms_url is
        "https://example.com/lms/" then application_instance.lms_host() will
        return "example.com".

        :raise ValueError: if the ApplicationInstance's lms_url can't be parsed
        """
        # urlparse() or .netloc will raise ValueError for some invalid URLs.
        lms_host = urlparse(self.lms_url).netloc

        # For some URLs urlparse(url).netloc returns an empty string.
        if not lms_host:
            raise ValueError(
                f"Couldn't parse self.lms_url ({self.lms_url}): urlparse() returned an empty netloc"
            )

        return lms_host

    def check_guid_aligns(self, tool_consumer_instance_guid):
        """
        Check there is no conflict between the provided GUID and ours.

        :raises ReusedConsumerKey: If the GUIDs are present and different
        """

        if (
            tool_consumer_instance_guid
            and self.tool_consumer_instance_guid
            and self.tool_consumer_instance_guid != tool_consumer_instance_guid
        ):
            # If we already have a LMS guid linked to the AI
            # and we found a different one report it to sentry
            raise ReusedConsumerKey(
                existing_guid=self.tool_consumer_instance_guid,
                new_guid=tool_consumer_instance_guid,
            )

    @property
    def lti_version(self) -> str:
        """
        LTI version of this installation based on the presence of a registration.

        The return values (LTI-1p0, "1.3.0) are the same the spec defines
        and will match the version parameter on lti launches.
        """
        if self.lti_registration_id and self.deployment_id:
            return "1.3.0"

        return "LTI-1p0"
