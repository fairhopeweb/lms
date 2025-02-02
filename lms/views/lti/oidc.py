"""
View for the second step of the OIDC authentication flow.

http://www.imsglobal.org/spec/security/v1p0/#step-2-authentication-request

We have to check we have a corresponding registration based on the `iss`
and `client_id` params and redirect back to the LMS.

The full flow is described at: http://www.imsglobal.org/spec/security/v1p0/#openid_connect_launch_flow

- Step 1: Third-party Initiated Login

The LMS launches our OIDC endpoint.

- Step 2: Authentication Request

We get the OIDC request and redirect accordingly (handled here)

- Step 3: Authentication Response

The redirect is handled and verified by the LMS

- Step 4: Resource is displayed

The actual LTI launch with an JWT token.

"""
import uuid
from urllib.parse import urlencode

from pyramid.httpexceptions import HTTPForbidden, HTTPFound
from pyramid.view import view_config
from webargs import fields

from lms.services import LTIRegistrationService
from lms.validation import PyramidRequestSchema


class OIDCRequestSchema(PyramidRequestSchema):
    location = "query_and_form"

    iss = fields.Str(required=True)
    client_id = fields.Str(required=False)

    target_link_uri = fields.Str(required=True)
    login_hint = fields.Str(required=True)
    lti_message_hint = fields.Str(required=True)


@view_config(
    route_name="lti.oidc",
    request_method=("POST", "GET"),
    schema=OIDCRequestSchema,
)
def oidc_view(request):
    params = request.parsed_params
    issuer, client_id = params["iss"], params.get("client_id")

    registration = request.find_service(LTIRegistrationService).get(issuer, client_id)
    if not registration:
        raise HTTPForbidden(
            f"""Registration not found. iss:'{issuer}', client_id:'{client_id}'"""
        )

    params = {
        # Hardcoded values from:
        # http://www.imsglobal.org/spec/security/v1p0/#step-2-authentication-request
        "scope": "openid",
        "response_type": "id_token",
        "response_mode": "form_post",
        "prompt": "none",
        "login_hint": params["login_hint"],
        "lti_message_hint": params["lti_message_hint"],
        # We might not have been provided the client id in the request, so use
        # the client id from the registration
        "client_id": registration.client_id,
        "state": uuid.uuid4().hex,
        "nonce": uuid.uuid4().hex,
        # The value will be configured when registering the tool in the LMS and
        # will be different depending on the message type. For example, it will
        # be an lti_launch endpoint for launches and content_item_selection /
        # deep linking for LMSs that support it while creating or editing
        # assignments.
        "redirect_uri": params["target_link_uri"],
    }
    return HTTPFound(location=f"{registration.auth_login_url}?{urlencode(params)}")
