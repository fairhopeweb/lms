from enum import Enum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from lms.db import BASE, varchar_enum


class EventType(BASE):
    __tablename__ = "event_type"

    class Type(str, Enum):
        CONFIGURED_LAUNCH = "configured_launch"
        DEEP_LINKING = "deep_linking"
        AUDIT_TRAIL = "audit"

    id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
    type = varchar_enum(Type)


class Event(BASE):
    """Model to store any relevant events that occur within the application."""

    __tablename__ = "event"

    id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

    timestamp = sa.Column(
        sa.DateTime(), server_default=sa.func.now(), nullable=False, index=True
    )
    """Time the event occurred, defaults to now() if not specified"""

    type_id = sa.Column(
        sa.Integer(), sa.ForeignKey("event_type.id", ondelete="cascade"), index=True
    )
    type = sa.orm.relationship("EventType")
    """One of EventType"""

    application_instance_id = sa.Column(
        sa.Integer(),
        sa.ForeignKey("application_instances.id", ondelete="cascade"),
        nullable=True,
        index=True,
    )
    application_instance = sa.orm.relationship("ApplicationInstance")
    """Which application instance this events relates to"""

    course_id = sa.Column(
        sa.Integer(),
        sa.ForeignKey("grouping.id", ondelete="cascade"),
        nullable=True,
        index=True,
    )
    course = sa.orm.relationship("Course", foreign_keys=[course_id])
    """If this event relates to one course only, which one"""

    assignment_id = sa.Column(
        sa.Integer(),
        sa.ForeignKey("assignment.id", ondelete="cascade"),
        nullable=True,
        index=True,
    )
    assignment = sa.orm.relationship("Assignment")
    """Which assignment this event relates to"""

    grouping_id = sa.Column(
        sa.Integer(), sa.ForeignKey("grouping.id", ondelete="cascade"), nullable=True
    )
    grouping = sa.orm.relationship("Grouping", foreign_keys=[grouping_id])
    """If this event belongs to one particular grouping, which one"""


class EventUser(BASE):
    """Relationship between events, users and their roles."""

    __tablename__ = "event_user"

    __table_args__ = (sa.UniqueConstraint("event_id", "user_id", "lti_role_id"),)

    id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

    event_id = sa.Column(
        sa.Integer(),
        sa.ForeignKey("event.id", ondelete="cascade"),
        nullable=False,
        primary_key=True,
    )
    event = sa.orm.relationship("Event")

    user_id = sa.Column(
        sa.Integer(),
        sa.ForeignKey("user.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    user = sa.orm.relationship("User")
    """Which user this events relates to"""

    lti_role_id = sa.Column(
        sa.Integer(),
        sa.ForeignKey("lti_role.id", ondelete="cascade"),
        nullable=True,
        index=True,
    )
    lti_role = sa.orm.relationship("LTIRole")
    """What role the user plays in event."""


class EventData(BASE):
    """Keep potentially large blobs of data about an event in a separate table."""

    __tablename__ = "event_data"

    event_id = sa.Column(
        sa.Integer(),
        sa.ForeignKey("event.id", ondelete="cascade"),
        nullable=False,
        primary_key=True,
    )
    event = sa.orm.relationship("Event")

    data = sa.Column(
        "extra",
        MutableDict.as_mutable(JSONB),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )
