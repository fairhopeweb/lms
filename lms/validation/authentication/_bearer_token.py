"""Schema for our bearer token-based LTI authentication."""
from datetime import timedelta

import marshmallow

from lms.models import LTIUser
from lms.services import JWTService
from lms.services.exceptions import ExpiredJWTError, InvalidJWTError
from lms.validation import ValidationError
from lms.validation._base import PyramidRequestSchema
from lms.validation.authentication._exceptions import (
    ExpiredSessionTokenError,
    InvalidSessionTokenError,
    MissingSessionTokenError,
)

__all__ = ("BearerTokenSchema",)


class BearerTokenSchema(PyramidRequestSchema):
    """
    Schema for our bearer token-based LTI authentication.

    Serializes models.LTIUser objects into signed and
    timestamped ``"Bearer <ENCODED_JWT>"`` strings, and deserializes these
    bearer strings back into models.LTIUser objects. The
    JWT signature and timestamp are verified during deserialization.

    Usage:

        >>> schema = BearerTokenSchema(request)

        >>> # Serialize an LTIUser (``request.lti_user`` in this example)
        >>> # into an authorization param value:
        >>> schema.authorization_param(request.lti_user)
        'Bearer eyJ...YoM'

        >>> # Deserialize the request's authorization param into an LTI user.
        >>> schema.lti_user()
        LTIUser(user_id='...', application_instance_id='...', ...)

    The above are convenience methods that wrap webargs and marshmallow. But
    this class is also a marshmallow schema and can be used via the usual
    webargs or marshmallow APIs. For example to serialize a dict and then
    deserialize the same dict back from its serialized form using marshmallow::

        >>> schema.dump(request.lti_user).data
        {'authorization': 'Bearer eyJ...YoM'}

        >>> schema.load({'authorization': 'Bearer eyJ...YoM'}).data
        LTIUser(user_id='...', application_instance_id='...', ...)

    Or to parse an models.LTIUser out of a Pyramid
    request's authorization param using webargs::

        >>> from webargs.pyramidparser import parser
        >>> parser.parse(s, request)
        LTIUser(user_id='...', application_instance_id='...', ...)
    """

    user_id = marshmallow.fields.Str(required=True)
    application_instance_id = marshmallow.fields.Int(required=True)
    roles = marshmallow.fields.Str(required=True)
    tool_consumer_instance_guid = marshmallow.fields.Str(required=True)
    display_name = marshmallow.fields.Str(required=True)
    email = marshmallow.fields.Str()

    def __init__(self, request):
        super().__init__(request)
        self._jwt_service = request.find_service(iface=JWTService)
        self._secret = request.registry.settings["jwt_secret"]

    def authorization_param(self, lti_user):
        """
        Return ``lti_user`` serialized into an authorization param.

        Returns a ``"Bearer: <ENCODED_JWT>"`` string suitable for use as the
        value of an authorization param.

        :arg lti_user: the LTI user to return an auth param for
        :type lti_user: LTIUser

        :rtype: str
        """
        return self.dump(lti_user)["authorization"]

    def lti_user(self, location):
        """
        Return an models.LTIUser from the request's authorization param.

        Verifies the signature and timestamp of the JWT in the request's
        authorization param, decodes the JWT, validates the JWT's payload, and
        returns an models.LTIUser from the payload.

        The authorization param can be in an HTTP header
        ``Authorization: Bearer <ENCODED_JWT>``, in a query string parameter
        ``?authorization=Bearer%20<ENCODED_JWT>``, or in a form field
        ``authorization=Bearer+<ENCODED_JWT>``. In the future we may add
        support for reading the authorization param from other parts of the
        request, such as from JSON body fields.

        :raise ExpiredSessionTokenError: if the request's Authorization header
          contains an expired JWT
        :raise MissingSessionTokenError: if the request does not contain an
          Authorization header
        :raise InvalidSessionTokenError: if the request contains an invalid
          Authorization header. For example if the Authorization header
          contains an invalid JWT, or if it doesn't have the required
          ``"Bearer <ENCODED_JWT>"`` format.
        :raise ValidationError: if the JWT's payload is invalid, for example if
          it's missing a required parameter

        :rtype: LTIUser
        """
        try:
            return self.parse(location=location)
        except ValidationError as error:
            try:
                authorization_error_message = error.messages[location]["authorization"][
                    0
                ]
            except KeyError:
                exc_class = ValidationError
            else:
                if authorization_error_message == "Expired session token":
                    exc_class = ExpiredSessionTokenError
                elif authorization_error_message == "Missing data for required field.":
                    exc_class = MissingSessionTokenError
                else:
                    exc_class = InvalidSessionTokenError
            raise exc_class(messages=error.messages) from error

    @marshmallow.post_dump
    def _encode_jwt(self, data, **_kwargs):
        """
        Return ``data`` encoded as a JWT enveloped in an authorization param.

        This uses a Marshmallow technique called "enveloping", see:

        https://marshmallow.readthedocs.io/en/2.x-line/extending.html#example-enveloping
        """
        token = self._jwt_service.encode_with_secret(
            data, self._secret, lifetime=timedelta(hours=24)
        )
        return {"authorization": f"Bearer {token}"}

    @marshmallow.pre_load
    def _decode_jwt(self, data, **_kwargs):
        """
        Return the payload from the JWT in the authorization param in ``data``.

        This uses a Marshmallow technique called "enveloping", see:

        https://marshmallow.readthedocs.io/en/2.x-line/extending.html#example-enveloping
        """
        if data["authorization"] == marshmallow.missing:
            raise marshmallow.ValidationError(
                "Missing data for required field.", "authorization"
            )

        jwt = data["authorization"][len("Bearer ") :]

        try:
            return self._jwt_service.decode_with_secret(jwt, self._secret)
        except ExpiredJWTError as err:
            raise marshmallow.ValidationError(
                "Expired session token", "authorization"
            ) from err
        except InvalidJWTError as err:
            raise marshmallow.ValidationError(
                "Invalid session token", "authorization"
            ) from err

    @marshmallow.post_load
    def _make_user(self, data, **_kwargs):
        # See https://marshmallow.readthedocs.io/en/2.x-line/quickstart.html#deserializing-to-objects
        return LTIUser(**data)
