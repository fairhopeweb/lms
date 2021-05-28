from lms.models import CanvasSection, Grouping
from lms.models._hashed_id import hashed_id


class GroupingService:
    def __init__(self, db, application_instance_service, course_service):
        self._db = db
        self._application_instance = application_instance_service.get()
        self._course_service = course_service

    def upsert(self, grouping):
        db_grouping = (
            self._db.query(Grouping)
            .filter_by(
                application_instance=grouping.application_instance,
                authority_provided_id=grouping.authority_provided_id,
                type=grouping.type,
            )
            .one_or_none()
        )
        if not db_grouping:
            self._db.add(grouping)
        else:
            # Update any fields that might have changed
            db_grouping.lms_name = grouping.lms_name
            db_grouping.extra = grouping.extra

        return db_grouping or grouping

    def canvas_section(
        self, tool_consumer_instance_guid, context_id, section_id, section_name
    ):
        """
        Create an HGroup for a course section.

        :param tool_consumer_instance_guid: Tool consumer GUID
        :param context_id: Course id the section is a part of
        :param section_id: A section id for a section group
        :param section_name: The name of the section
        """

        section_authority_provided_id = hashed_id(
            tool_consumer_instance_guid, context_id, section_id
        )

        course_authority_provided_id = hashed_id(
            tool_consumer_instance_guid, context_id
        )

        course = self._course_service.get(course_authority_provided_id)

        return self.upsert(
            CanvasSection(
                application_instance=self._application_instance,
                authority_provided_id=section_authority_provided_id,
                lms_id=section_id,
                lms_name=section_name,
                parent=course,
            )
        )


def factory(_context, request):
    return GroupingService(
        request.db,
        request.find_service(name="application_instance"),
        request.find_service(name="course"),
    )
