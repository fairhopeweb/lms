from unittest.mock import create_autospec, sentinel

import pytest
from h_matchers import Any

from lms.models import Grouping, LTIParams
from lms.product import Product
from lms.resources import LTILaunchResource, OAuth2RedirectResource
from lms.resources._js_config import JSConfig
from lms.services import HAPIError
from tests import factories

pytestmark = pytest.mark.usefixtures(
    "grading_info_service",
    "grant_token_service",
    "h_api",
    "vitalsource_service",
    "jstor_service",
)


class TestFilePickerMode:
    def test_it(self, js_config):
        js_config.enable_file_picker_mode(sentinel.form_action, sentinel.form_fields)
        config = js_config.asdict()

        assert config == Any.dict.containing(
            {
                "mode": "content-item-selection",
                "filePicker": Any.dict.containing(
                    {
                        "formAction": sentinel.form_action,
                        "formFields": sentinel.form_fields,
                    }
                ),
            }
        )

    @pytest.mark.parametrize(
        "config_function,key",
        (
            ("blackboard_config", "blackboard"),
            ("canvas_config", "canvas"),
            ("google_files_config", "google"),
            ("microsoft_onedrive", "microsoftOneDrive"),
            ("vital_source_config", "vitalSource"),
            ("jstor_config", "jstor"),
        ),
    )
    def test_it_adds_picker_config(
        self,
        js_config,
        context,
        pyramid_request,
        FilePickerConfig,
        config_function,
        key,
    ):
        js_config.enable_file_picker_mode(sentinel.form_action, sentinel.form_fields)
        config = js_config.asdict()

        config_provider = getattr(FilePickerConfig, config_function)
        assert config["filePicker"][key] == config_provider.return_value
        config_provider.assert_called_once_with(
            context,
            pyramid_request,
            context.application_instance,
        )

    @pytest.fixture(autouse=True)
    def FilePickerConfig(self, patch):
        return patch("lms.resources._js_config.FilePickerConfig")


class TestEnableLTILaunchMode:
    def test_it(self, bearer_token_schema, context, grant_token_service, js_config):
        js_config.enable_lti_launch_mode()

        assert js_config.asdict() == {
            "api": {
                "authToken": bearer_token_schema.authorization_param.return_value,
                "sync": None,
            },
            "canvas": {},
            "debug": {"tags": [Any.string.matching("^role:.*")]},
            "dev": False,
            "hypothesisClient": {
                "services": [
                    {
                        "allowFlagging": False,
                        "allowLeavingGroups": False,
                        "apiUrl": "https://example.com/api/",
                        "authority": "TEST_AUTHORITY",
                        "enableShareLinks": False,
                        "grantToken": grant_token_service.generate_token.return_value,
                        "groups": [context.course.groupid.return_value],
                    }
                ]
            },
            "mode": "basic-lti-launch",
            "rpcServer": {"allowedOrigins": ["http://localhost:5000"]},
        }


class TestAddDocumentURL:
    """Unit tests for JSConfig.add_document_url()."""

    def test_it_adds_the_via_url(self, js_config, pyramid_request, via_url):
        js_config.add_document_url("example_document_url")

        via_url.assert_called_once_with(pyramid_request, "example_document_url")
        assert js_config.asdict()["viaUrl"] == via_url.return_value

    def test_it_adds_the_viaUrl_api_config_for_Blackboard_documents(
        self, js_config, pyramid_request
    ):
        js_config.add_document_url("blackboard://content-resource/xyz123")

        assert js_config.asdict()["api"]["viaUrl"] == {
            "authUrl": "http://example.com/api/blackboard/oauth/authorize",
            "product": pyramid_request.product.family,
            "path": "/api/blackboard/courses/test_course_id/via_url?document_url=blackboard%3A%2F%2Fcontent-resource%2Fxyz123",
        }

    def test_vitalsource_sets_config(self, js_config, vitalsource_service):
        vitalsource_url = "vitalsource://book/bookID/book-id/cfi//abc"

        js_config.add_document_url(vitalsource_url)

        vitalsource_service.get_launch_url.assert_called_with(vitalsource_url)
        assert js_config.asdict()["vitalSource"] == {
            "launchUrl": vitalsource_service.get_launch_url.return_value
        }

    def test_jstor_sets_config(self, js_config, jstor_service, pyramid_request):
        jstor_url = "jstor://DOI"

        js_config.add_document_url(jstor_url)

        jstor_service.via_url.assert_called_with(pyramid_request, jstor_url)
        assert js_config.asdict()["viaUrl"] == jstor_service.via_url.return_value

    def test_it_adds_the_viaUrl_api_config_for_Canvas_documents(
        self, js_config, pyramid_request
    ):
        course_id, file_id = "125", "100"
        pyramid_request.params["custom_canvas_course_id"] = course_id
        pyramid_request.params["file_id"] = file_id

        js_config.add_document_url(
            f"canvas://file/course/{course_id}/file_id/{file_id}"
        )

        assert js_config.asdict()["api"]["viaUrl"] == {
            "authUrl": "http://example.com/api/canvas/oauth/authorize",
            "product": pyramid_request.product.family,
            "path": "/api/canvas/assignments/TEST_RESOURCE_LINK_ID/via_url",
        }


class TestAddCanvasSpeedgraderSettings:
    @pytest.mark.parametrize("group_set", (sentinel.group_set, None))
    def test_it(self, js_config, pyramid_request, context, group_set):
        pyramid_request.feature.return_value = False
        if group_set:
            pyramid_request.params["group_set"] = group_set

        js_config.add_canvas_speedgrader_settings(sentinel.document_url)

        config = js_config.asdict()
        assert config["canvas"]["speedGrader"]["submissionParams"] == {
            "h_username": pyramid_request.lti_user.h_user.username,
            "group_set": group_set,
            "document_url": sentinel.document_url,
            "resource_link_id": pyramid_request.params["resource_link_id"],
            "lis_result_sourcedid": context.lti_params["lis_result_sourcedid"],
            "lis_outcome_service_url": context.lti_params["lis_outcome_service_url"],
            "learner_canvas_user_id": context.lti_params["custom_canvas_user_id"],
        }
        assert not config.get("hypothesisClient")

    def test_it_adds_report_activity_if_submit_on_annotation_enabled(
        self, js_config, pyramid_request
    ):
        pyramid_request.feature.return_value = True

        js_config.add_canvas_speedgrader_settings(sentinel.document_url)

        pyramid_request.feature.assert_called_once_with("submit_on_annotation")
        # This doesn't get flushed out to the config until we call
        # `enable_lti_launch_mode` so we have to inspect it directly
        # pylint: disable=protected-access
        assert js_config._hypothesis_client["reportActivity"] == {
            "method": "reportActivity",
            "events": ["create", "update"],
        }


class TestEnableGradingBar:
    def test_it(self, js_config, context, grading_info_service):
        js_config.enable_grading_bar()

        grading_info_service.get_by_assignment.assert_called_once_with(
            context_id="test_course_id",
            application_instance=context.application_instance,
            resource_link_id="TEST_RESOURCE_LINK_ID",
        )

        assert js_config.asdict()["grading"] == {
            "enabled": True,
            "courseName": context.lti_params["context_title"],
            "assignmentName": context.lti_params["resource_link_title"],
            "students": [
                {
                    "userid": f"acct:{grading_info.h_username}@TEST_AUTHORITY",
                    "displayName": grading_info.h_display_name,
                    "lmsId": grading_info.user_id,
                    "LISResultSourcedId": grading_info.lis_result_sourcedid,
                    "LISOutcomeServiceUrl": grading_info.lis_outcome_service_url,
                }
                for grading_info in grading_info_service.get_by_assignment.return_value
            ],
        }

    @pytest.fixture
    def grading_info_service(self, grading_info_service):
        grading_info_service.get_by_assignment.return_value = (
            factories.GradingInfo.create_batch(3)
        )
        return grading_info_service

    @pytest.fixture(autouse=True)
    def pyramid_request(self, pyramid_request):
        pyramid_request.params["resource_link_title"] = "test_assignment_name"

        return pyramid_request


class TestSetFocusedUser:
    def test_it_sets_the_focused_user_if_theres_a_focused_user_param(
        self, h_api, js_config
    ):
        js_config.set_focused_user(sentinel.focused_user)

        h_api.get_user.assert_called_once_with(sentinel.focused_user)
        assert js_config.asdict()["hypothesisClient"]["focus"] == {
            "user": {
                "username": sentinel.focused_user,
                "displayName": h_api.get_user.return_value.display_name,
            },
        }

    def test_display_name_falls_back_to_a_default_value(self, h_api, js_config):
        h_api.get_user.side_effect = HAPIError()

        js_config.set_focused_user(sentinel.focused_user)

        assert (
            js_config.asdict()["hypothesisClient"]["focus"]["user"]["displayName"]
            == "(Couldn't fetch student name)"
        )

    @pytest.fixture
    def js_config(self, js_config):
        # `set_focused_user` needs the `hypothesisClient` section to exist
        js_config.enable_lti_launch_mode()

        return js_config


class TestJSConfigAuthToken:
    """Unit tests for the "authToken" sub-dict of JSConfig."""

    def test_it(
        self, authToken, bearer_token_schema, BearerTokenSchema, pyramid_request
    ):
        BearerTokenSchema.assert_called_once_with(pyramid_request)
        bearer_token_schema.authorization_param.assert_called_once_with(
            pyramid_request.lti_user
        )
        assert authToken == bearer_token_schema.authorization_param.return_value

    @pytest.fixture
    def authToken(self, config):
        return config["api"]["authToken"]


class TestJSConfigAPISync:
    """Unit tests for the api.sync sub-dict of JSConfig."""

    @pytest.mark.usefixtures("with_sections_on", "with_speed_grader")
    def test_when_is_canvas(self, sync, context):
        assert sync == {
            "authUrl": "http://example.com/api/canvas/oauth/authorize",
            "path": "/api/sync",
            "data": {
                "lms": {
                    "product": Product.Family.CANVAS,
                },
                "context_id": "test_context_id",
                "group_set_id": context.group_set_id,
                "gradingStudentId": sentinel.learner_canvas_user_id,
            },
        }

    @pytest.mark.usefixtures("blackboard_group_launch")
    def test_when_is_blackboard(self, sync, context):
        assert sync == {
            "authUrl": "http://example.com/api/blackboard/oauth/authorize",
            "path": "/api/sync",
            "data": {
                "lms": {
                   "product": Product.Family.BLACKBOARD,
                },
                "context_id": "test_context_id",
                "group_set_id": context.group_set_id,
                "gradingStudentId": None,
            },
        }

    def test_its_None_if_section_and_groups_arent_enabled(self, sync):
        assert sync is None

    @pytest.fixture
    def sync(self, config, js_config):
        # Call enable_lti_launch_mode() so that the api.sync section gets
        # inserted into the config.
        js_config.enable_lti_launch_mode()

        return config["api"]["sync"]

    @pytest.fixture
    def blackboard_group_launch(self, context, pyramid_request):
        context.grouping_type = Grouping.Type.GROUP
        pyramid_request.product.family = Product.Family.BLACKBOARD

    @pytest.fixture()
    def with_speed_grader(self, pyramid_request):
        pyramid_request.params[
            "learner_canvas_user_id"
        ] = sentinel.learner_canvas_user_id

    @pytest.fixture
    def pyramid_request(self, pyramid_request):
        pyramid_request.params.clear()
        pyramid_request.params.update({"context_id": "test_context_id"})
        return pyramid_request


class TestJSConfigDebug:
    """Unit tests for the "debug" sub-dict of JSConfig."""

    @pytest.mark.usefixtures("user_is_learner")
    def test_it_contains_debugging_info_about_the_users_role(self, config):
        assert "role:learner" in config["tags"]

    @pytest.fixture
    def config(self, config):
        return config["debug"]


class TestJSConfigHypothesisClient:
    """Unit tests for the "hypothesisClient" sub-dict of JSConfig."""

    def test_it(self, config, grant_token_service, context, pyramid_request):
        grant_token_service.generate_token.assert_called_with(
            pyramid_request.lti_user.h_user
        )

        assert config["services"] == [
            {
                "allowFlagging": False,
                "allowLeavingGroups": False,
                "apiUrl": "https://example.com/api/",
                "authority": "TEST_AUTHORITY",
                "enableShareLinks": False,
                "grantToken": grant_token_service.generate_token.return_value,
                "groups": [context.course.groupid.return_value],
            }
        ]

    @pytest.mark.usefixtures("with_sections_on")
    def test_configures_the_client_to_fetch_the_groups_over_RPC_with_sections(
        self, config
    ):
        assert config["services"][0]["groups"] == "$rpc:requestGroups"

    @pytest.mark.usefixtures("with_groups_on")
    def test_it_configures_the_client_to_fetch_the_groups_over_RPC_with_groups(
        self, config
    ):
        assert config["services"][0]["groups"] == "$rpc:requestGroups"

    @pytest.mark.usefixtures("with_provisioning_disabled")
    def test_it_is_empty_if_provisioning_feature_is_disabled(self, config):
        assert config == {}

    def test_it_is_mutable(self, config):
        config.update({"a_key": "a_value"})

        assert config["a_key"] == "a_value"

    @pytest.fixture
    def config(self, config, js_config):
        # Call enable_lti_launch_mode() so that the "hypothesisClient" section
        # gets inserted into the config.
        js_config.enable_lti_launch_mode()

        return config["hypothesisClient"]


class TestJSConfigRPCServer:
    """Unit tests for the "rpcServer" sub-dict of JSConfig."""

    def test_it(self, config):
        assert config == {"allowedOrigins": ["http://localhost:5000"]}

    @pytest.fixture
    def config(self, config, js_config):
        # Call enable_lti_launch_mode() so that the "rpcServer" section gets
        # inserted into the config.
        js_config.enable_lti_launch_mode()

        return config["rpcServer"]


class TestEnableOAuth2RedirectErrorMode:
    def test_it(self, js_config, pyramid_request):
        js_config.enable_oauth2_redirect_error_mode(
            "auth_route",
            sentinel.error_code,
            sentinel.error_details,
            sentinel.canvas_scopes,
        )
        config = js_config.asdict()

        assert config["mode"] == JSConfig.Mode.OAUTH2_REDIRECT_ERROR
        assert config["OAuth2RedirectError"] == {
            "authUrl": "http://example.com/auth?authorization=Bearer%3A+token_value",
            "product": pyramid_request.product.family,
            "errorCode": sentinel.error_code,
            "errorDetails": sentinel.error_details,
            "canvasScopes": sentinel.canvas_scopes,
        }

    @pytest.mark.usefixtures("with_no_user")
    def test_if_theres_no_authenticated_user_it_sets_authUrl_to_None(self, js_config):
        js_config.enable_oauth2_redirect_error_mode(auth_route="auth_route")
        config = js_config.asdict()

        assert config["OAuth2RedirectError"]["authUrl"] is None

    def test_it_omits_errorDetails_if_no_error_details_argument_is_given(
        self, js_config
    ):
        js_config.enable_oauth2_redirect_error_mode(auth_route="auth_route")
        config = js_config.asdict()

        assert "errorDetails" not in config["OAuth2RedirectError"]

    def test_canvas_scopes_defaults_to_an_empty_list(self, js_config):
        js_config.enable_oauth2_redirect_error_mode(auth_route="auth_route")
        config = js_config.asdict()

        assert config["OAuth2RedirectError"]["canvasScopes"] == []

    @pytest.fixture
    def context(self):
        return create_autospec(OAuth2RedirectResource, spec_set=True, instance=True)

    @pytest.fixture(autouse=True)
    def routes(self, pyramid_config):
        pyramid_config.add_route("auth_route", "/auth")


class TestAddDeepLinkingAPI:
    def test_it_adds_deep_linking_v11(self, js_config, context):
        context.lti_params = {
            "content_item_return_url": sentinel.content_item_return_url,
        }

        js_config.add_deep_linking_api()

        config = js_config.asdict()
        assert config["filePicker"]["deepLinkingAPI"] == {
            "path": "/lti/1.1/deep_linking/form_fields",
            "data": {
                "content_item_return_url": sentinel.content_item_return_url,
            },
        }

    @pytest.mark.usefixtures("with_lti_13")
    def test_it_adds_deep_linking_v13(self, js_config, context):
        context.lti_params = {
            "deep_linking_settings": sentinel.deep_linking_settings,
            "content_item_return_url": sentinel.content_item_return_url,
        }

        js_config.add_deep_linking_api()

        config = js_config.asdict()
        assert config["filePicker"]["deepLinkingAPI"] == {
            "path": "/lti/1.3/deep_linking/form_fields",
            "data": {
                "content_item_return_url": sentinel.content_item_return_url,
                "deep_linking_settings": sentinel.deep_linking_settings,
            },
        }

    @pytest.fixture
    def with_lti_13(self, context):
        # Make the application instance `lti_version` return "1.3.0"
        context.application_instance.lti_registration_id = 100


class TestEnableErrorDialogMode:
    def test_it(self, js_config):
        js_config.enable_error_dialog_mode(sentinel.error_code, sentinel.error_details)
        config = js_config.asdict()

        assert config["mode"] == JSConfig.Mode.ERROR_DIALOG
        assert config["errorDialog"] == {
            "errorCode": sentinel.error_code,
            "errorDetails": sentinel.error_details,
        }

    def test_it_omits_errorDetails_if_no_error_details_argument_is_given(
        self, js_config
    ):
        js_config.enable_error_dialog_mode(sentinel.error_code)
        config = js_config.asdict()

        assert "errorDetails" not in config["errorDialog"]

    @pytest.fixture
    def context(self):
        return create_autospec(OAuth2RedirectResource, spec_set=True, instance=True)


@pytest.fixture(autouse=True)
def BearerTokenSchema(patch):
    BearerTokenSchema = patch("lms.resources._js_config.BearerTokenSchema")
    BearerTokenSchema.return_value.authorization_param.return_value = (
        "Bearer: token_value"
    )
    return BearerTokenSchema


@pytest.fixture
def bearer_token_schema(BearerTokenSchema):
    return BearerTokenSchema.return_value


@pytest.fixture
def js_config(context, pyramid_request):
    return JSConfig(context, pyramid_request)


@pytest.fixture
def config(js_config):
    return js_config.asdict()


@pytest.fixture
def context(pyramid_request, application_instance):
    return create_autospec(
        LTILaunchResource,
        spec_set=True,
        instance=True,
        is_canvas=True,
        sections_enabled=False,
        grouping_type=Grouping.Type.COURSE,
        course=create_autospec(Grouping, instance=True, spec_set=True),
        lti_params=LTIParams(pyramid_request.params),
        application_instance=application_instance,
    )


@pytest.fixture
def with_sections_on(context, pyramid_request):
    context.grouping_type = Grouping.Type.SECTION
    pyramid_request.product.family = Product.Family.CANVAS


@pytest.fixture
def with_groups_on(context):
    context.grouping_type = Grouping.Type.GROUP


@pytest.fixture
def with_no_user(pyramid_request):
    pyramid_request.lti_user = None


@pytest.fixture
def with_provisioning_disabled(context):
    context.application_instance.provisioning = False


@pytest.fixture
def pyramid_request(pyramid_request):
    pyramid_request.params.update(
        {
            "lis_result_sourcedid": "example_lis_result_sourcedid",
            "lis_outcome_service_url": "example_lis_outcome_service_url",
            "context_id": "test_course_id",
            "custom_canvas_course_id": "test_course_id",
            "custom_canvas_user_id": "test_user_id",
        }
    )
    return pyramid_request


@pytest.fixture(autouse=True)
def via_url(patch):
    return patch("lms.resources._js_config.via_url")


@pytest.fixture(autouse=True)
def GroupInfo(patch):
    group_info_class = patch("lms.resources._js_config.GroupInfo")
    group_info_class.columns.return_value = ["context_id", "custom_canvas_course_id"]
    return group_info_class
