__version__ = (2, 0, 10)

import os
import re
import logging
from bottle import request, response, HTTPResponse, json_dumps, static_file
from bravado_core.exception import MatchingResponseNotFound, SwaggerSecurityValidationError
from bravado_core.request import IncomingRequest, unmarshal_request
from bravado_core.response import OutgoingResponse, validate_response, get_response_spec
from bravado_core.spec import Spec
from jsonschema import ValidationError
from six.moves.urllib.parse import urljoin, urlparse
from six import string_types, binary_type
from bottle import SimpleTemplate


SWAGGER_UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
        'vendor', 'swagger-ui-3.24.1-dist')
SWAGGER_UI_INDEX_TEMPLATE_PATH = os.path.join(SWAGGER_UI_DIR, 'index.html.st')

with open(SWAGGER_UI_INDEX_TEMPLATE_PATH, 'r') as f:
    SWAGGER_UI_INDEX_TEMPLATE = f.read()


plugin_logger = logging.getLogger(__name__)


def render_index_html(swagger_spec_url, validator_url=None):
    return SimpleTemplate(SWAGGER_UI_INDEX_TEMPLATE).render(
        swagger_spec_url=swagger_spec_url,
        validator_url=json_dumps(validator_url)
    )


def _error_response(status, e):
    response.status = status
    return {"code": status, "message": str(e)}


def default_server_error_handler(e):
    """
    The default error handler function when the request callback throws
    and exception.

    Returns a JSON payload of

    {"code": 500, "message": str(e)}

    And sets the status code to 500.

    :param e: The exception that was thrown by the request handler.
    :type e: BaseException
    :return: The response payload.
    :rtype: dict
    """
    return _error_response(500, e)


def default_bad_request_handler(e):
    """
    The default error handler function for request validation
    failures.

    Returns a JSON payload of

    {"code": 400, "message": str(e)}

    And sets the status code to 400.

    :param e: The exception that was thrown Bravado Core upon request validation failure.
    :type e: BaseException
    :return: The response payload.
    :rtype: dict
    """
    return _error_response(400, e)


def default_invalid_security_handler(e):
    """
    The default error handler function for lack of auth
    failures.

    Returns a JSON payload of

    {"code": 401, "message": str(e)}

    And sets the status code to 401.

    :param e: The exception that was thrown Bravado Core upon request validation failure.
    :type e: BaseException
    :return: The response payload.
    :rtype: dict
    """
    return _error_response(401, e)


def default_not_found_handler(r):
    """
    The default error handler function for route not found failures.

    Returns a JSON payload of

    {"code": 404, "message": str(r)}

    And sets the status code to 404.

    :param r: The Bottle route that was triggered.
    :type r: bottle.Route
    :return: The response payload.
    :rtype: dict
    """
    return _error_response(404, r)


class SecurityPatchedOperation(object):
    def __init__(self, core_op):
        self._core_op = core_op

    def __repr__(self):
        return repr(self._core_op)

    @property
    def security_specs(self):
        return []

    @property
    def security_requirements(self):
        return []

    def __getattr__(self, item):
        return getattr(self._core_op, item)

    def __setattr__(self, key, value):
        if key == "_core_op":
            self.__dict__[key] = value
        else:
            return setattr(self._core_op, key, value)


class SwaggerPlugin(object):
    """
    This plugin allows the user to use Swagger 2.0 and Bravado Core to write a REST API with validation
    and automatic marshalling and unmarshalling.

    This may be used in a Bottle application by installing it using the ``install`` method:

        >>> from bottle import Bottle
        >>> from bottle_swagger import SwaggerPlugin
        >>> my_app = Bottle()
        >>> my_swagger_def = {}  # This should be your actual swagger spec, as a Python dict.
        >>> my_plugin = SwaggerPlugin(my_swagger_def, serve_swagger_ui=True)
        >>> my_app.install(my_plugin)

    Constructor Parameters:

    * ``swagger_def`` -- (dict) The raw Swagger 2.0 specification, as a Python dictionary.
    * ``validate_swagger_spec`` -- (bool) Should plugin validate the given Swagger specification?
    * ``validate_requests`` -- (bool) Should the plugin validate incoming requests for defined Swagger routes?
    * ``validate_responses`` -- (bool) Should the plugin validate outoging requests for defined Swagger routes?
    * ``use_bravado_models`` -- (bool) Should the plugin use Bravado's models or raw dictionaries for the swagger_data
        attached to the requests?
    * ``user_defined_formats`` -- (bool) A list of any custom formats (as defined by Bravado-Core) for our Swagger Spec.
    * ``include_missing_properties`` -- (bool) Should we include any missing properties as None?
    * ``default_type_to_object`` -- (bool) If a type isn't given for a Swagger property should it default to "object"?
    * ``internally_dereference_refs`` -- (bool) Should Bravado fully derefence $refs (for a performance speed up)?
    * ``ignore_undefined_api_routes`` -- (bool) Should we ignore undefined API routes, and trigger the
        swagger_op_not_found handler?
    * ``ignore_security_definitions`` -- (bool) Should we ignore the security requirements specified in the swagger
        spec? This allows you to use things like Cookie auth as an undocumented fallback without Bravado complaining.
    * ``auto_jsonify`` -- (bool) Should we automatically convert data returned from our callbacks to JSON? Bottle
        normally will attempt to convert only objects, but we can do better.
    * ``invalid_request_handler`` -- (Exception -> HTTP Response) This handler is triggered when the
        request validation fails.
    * ``invalid_response_handler`` -- (Exception -> HTTP Response) This handler is triggered when
        the response validation fails.
    * ``invalid_security_handler`` -- (Exception -> HTTP Response) This handler is triggered when
        no valid forms of authentication matching the Swagger spec were in the incoming request. This is
        ignored if ``ignore_security_definitions`` is set to True.
    * ``swagger_op_not_found_handler`` -- (bottle.Route -> HTTP Response) This handler is triggered if the
        route isn't found for the API subpath, and ignore_missing_routes has been set True.
    * ``exception_handler`` -- (Base Exception -> HTTP Response.) This handler is triggered if the
        request callback threw an exception.
    * ``swagger_base_path`` -- (str) Override the base path for the API specified in the swagger spec?
    * ``adjust_api_base_path`` - Boolean (default ``True``) Adjust the basePath reported by the swagger.json.
        This is important if your WSGI application is running under a subpath.
    * ``serve_swagger_schema`` -- (bool) Should we serve the Swagger schema?
    * ``swagger_schema_suburl`` -- (str) The subpath in the API to serve the swagger schema.
    * ``serve_swagger_ui`` -- (bool) Should we also serve a copy of Swagger UI?
    * ``swagger_ui_suburl`` -- (str) The subpath from the API to serve the integrate Swagger UI up at.
    * ``swagger_ui_validator_url`` -- (str) The URL for a Swagger spec validator. By default this is None (i.e. off).
    * ``extra_bravado_config`` -- (object) Any additional Bravado configuration items you may want.
    """
    DEFAULT_SWAGGER_SCHEMA_SUBURL = '/swagger.json'
    DEFAULT_SWAGGER_UI_SUBURL = '/ui/'

    name = 'swagger'
    api = 2

    def __init__(self, swagger_def,
                 validate_swagger_spec=True,
                 validate_requests=True,
                 validate_responses=True,
                 use_bravado_models=True,
                 user_defined_formats=None,
                 include_missing_properties=True,
                 default_type_to_object=False,
                 internally_dereference_refs=False,
                 ignore_undefined_api_routes=False,
                 ignore_security_definitions=False,
                 auto_jsonify=True,
                 invalid_request_handler=default_bad_request_handler,
                 invalid_response_handler=default_server_error_handler,
                 invalid_security_handler=default_invalid_security_handler,
                 swagger_op_not_found_handler=default_not_found_handler,
                 exception_handler=default_server_error_handler,
                 swagger_base_path=None,
                 adjust_api_base_path=True,
                 serve_swagger_schema=True,
                 swagger_schema_suburl=DEFAULT_SWAGGER_SCHEMA_SUBURL,
                 serve_swagger_ui=False,
                 swagger_ui_schema_url=None,
                 swagger_ui_suburl=DEFAULT_SWAGGER_UI_SUBURL,
                 swagger_ui_validator_url=None,
                 extra_bravado_config=None):
        """
        Add Swagger validation to your Bottle application.

        :param swagger_def: The raw Swagger 2.0 specification, as a Python dictionary.
        :type swagger_def: dict
        :param validate_swagger_spec: Should plugin validate the given Swagger specification?
        :type validate_swagger_spec: bool
        :param validate_requests: Should the plugin validate incoming requests for defined Swagger routes?
        :type validate_requests: bool
        :param validate_responses: Should the plugin validate outoging requests for defined Swagger routes?
        :type validate_responses: bool
        :param use_bravado_models: Should the plugin use Bravado's models or raw dictionaries for the swagger_data
            attached to the requests?
        :type use_bravado_models: bool
        :param user_defined_formats: A list of any custom formats (as defined by Bravado-Core) for our Swagger Spec.
        :type user_defined_formats: bool
        :param include_missing_properties: Should we include any missing properties as None?
        :type: include_missing_properties: bool
        :param default_type_to_object: If a type isn't given for a Swagger property should it default to "object"?
        :type default_type_to_object: bool
        :param internally_dereference_refs: Should Bravado fully derefence $refs (for a performance speed up)?
        :type internally_dereference_refs: bool
        :param ignore_undefined_api_routes: Should we ignore undefined API routes, and trigger the
            swagger_op_not_found handler?
        :type ignore_undefined_api_routes: bool
        :param ignore_security_definitions: Should we ignore the set security definitions? This might make sense if
                                            you also want to permit Cookie auth (which is not available in OpenAPI 2).
        :type ignore_security_definitions: bool
        :param auto_jsonify: Should we automatically convert data returned from our callbacks to JSON? Bottle
            normally will attempt to convert only objects, but we can do better.
        :type auto_jsonify: bool
        :param invalid_request_handler: This handler is triggered when the request validation fails.
        :type invalid_request_handler: BaseException -> HTTP Response
        :param invalid_response_handler: This handler is triggered when the response validation fails.
        :type invalid_response_handler: BaseException -> HTTP Response
        :param invalid_security_handler: This handler is triggered when no means of authentication
                                         were found for the request.
        :type invalid_security_handler: BaseException -> HTTP Response
        :param swagger_op_not_found_handler: This handler is triggered if the route isn't found for the API subpath,
           and ignore_missing_routes has been set True.
        :type swagger_op_not_found_handler: bottle.Route -> HTTP Response
        :param exception_handler: This handler is triggered if the request callback threw an exception.
        :type exception_handler: BaseException -> HTTP Response.
        :param swagger_base_path: Override the base path for the API specified in the swagger spec/
        :type swagger_base_path: str
        :param adjust_api_base_path: Adjust the basePath reported by the swagger.json. This is important if your
            WSGI application is running under a subpath.
        :type adjust_api_base_path: bool
        :param serve_swagger_schema: Should we serve the Swagger schema?
        :type serve_swagger_schema: bool
        :param swagger_schema_suburl: The subpath in the API to serve the swagger schema.
        :type swagger_schema_suburl: str
        :param serve_swagger_ui: Should we also serve a copy of Swagger UI?
        :type serve_swagger_ui: bool
        :param swagger_ui_schema_url: If this is not None, this will be used to set the default URL used with the
            bundled Swagger UI instance, if enabled. If it is a string, this will be the new Swagger spec URL; if this
            is an arity-0 callable, this will be evaluated each time the UI is served up, and result will be the
            spec URL that is served up. Default: None
        :type swagger_ui_schema_url: NoneType | str | -> str
        :param swagger_ui_suburl: The subpath from the API to serve the integrate Swagger UI up at.
        :type swagger_ui_suburl: str
        :param swagger_ui_validator_url: The URL for a Swagger validator instance. If None, validation in the UI is off.
            If this is set to an arity 0 callable, this will be evaluated each time the Swagger UI is constructed.
        :type swagger_ui_validator_url: str | -> str | NoneType
        :param extra_bravado_config: Any additional Bravado configuration items you may want.
        :type extra_bravado_config: object
        """
        plugin_logger.debug("Initializing Bottle Swagger Plugin...")
        swagger_def = dict(swagger_def)
        if swagger_base_path is not None:
            swagger_def.update(basePath=swagger_base_path)

        self.ignore_undefined_routes = ignore_undefined_api_routes
        self.ignore_security_definitions = ignore_security_definitions
        self.auto_jsonify = auto_jsonify
        self.invalid_request_handler = invalid_request_handler
        self.invalid_response_handler = invalid_response_handler
        self.invalid_security_handler = invalid_security_handler
        self.swagger_op_not_found_handler = swagger_op_not_found_handler
        self.exception_handler = exception_handler
        self.serve_swagger_ui = serve_swagger_ui
        self.swagger_ui_schema_url = swagger_ui_schema_url

        self.serve_swagger_schema = serve_swagger_schema
        if not serve_swagger_schema and swagger_ui_schema_url is None and serve_swagger_ui:
            plugin_logger.warning(
                "Swagger UI enabled, but plugin instance has no configured swagger specification source!"
            )
            plugin_logger.warning(
                "Defaulting to an empty Swagger specification source for the UI, this is likely a misconfiguration!"
            )

        self.swagger_ui_validator_url = swagger_ui_validator_url

        self.swagger_schema_suburl = swagger_schema_suburl
        self.swagger_ui_suburl = swagger_ui_suburl
        self.bravado_config = extra_bravado_config or {}
        self.bravado_config.update({
            'validate_swagger_spec': validate_swagger_spec,
            'validate_requests': validate_requests,
            'validate_responses': validate_responses,
            'use_models': use_bravado_models,
            'formats': user_defined_formats or [],
            'include_missing_properties': include_missing_properties,
            'default_type_to_object': default_type_to_object,
            'internally_dereference_refs': internally_dereference_refs
        })

        self.swagger = Spec.from_dict(swagger_def, config=self.bravado_config)
        self.swagger_base_path = swagger_base_path or urlparse(self.swagger.api_url).path or '/'
        self.adjust_api_base_path = adjust_api_base_path

        fixed_base_path = (self.swagger_base_path.rstrip("/")) + "/"
        self.swagger_schema_url = urljoin(fixed_base_path, self.swagger_schema_suburl.lstrip("/"))
        self.swagger_ui_base_url = urljoin(fixed_base_path, self.swagger_ui_suburl.lstrip("/"))
        plugin_logger.debug("Bottle Swagger Plugin Initialization Completed!")

    def apply(self, callback, route):
        def wrapper(*args, **kwargs):
            return self._swagger_validate(callback, route, *args, **kwargs)

        return wrapper

    def setup(self, app):
        if self.serve_swagger_schema:
            @app.get(self.swagger_schema_url)
            def swagger_schema():
                spec_dict = self.swagger.spec_dict
                if self.adjust_api_base_path and "basePath" in spec_dict:
                    spec_dict["basePath"] = urljoin(
                        urljoin("/", request.environ.get('SCRIPT_NAME', '').strip('/') + '/'),
                        self.swagger_base_path.lstrip("/")
                    )
                return spec_dict

        if self.serve_swagger_ui:
            @app.get(self.swagger_ui_base_url)
            def swagger_ui_index():
                if self.swagger_ui_schema_url is not None and callable(self.swagger_ui_schema_url):
                    schema_url = self.swagger_ui_schema_url()
                elif self.swagger_ui_schema_url is not None:
                    schema_url = self.swagger_ui_schema_url
                elif self.serve_swagger_schema:
                    schema_url = app.get_url(self.swagger_schema_url)
                else:
                    schema_url = ""
                if self.swagger_ui_validator_url is not None and callable(self.swagger_ui_validator_url):
                    validator_url = self.swagger_ui_validator_url()
                else:
                    validator_url = self.swagger_ui_validator_url
                return render_index_html(
                    schema_url,
                    validator_url=validator_url
                )

            @app.get(urljoin(self.swagger_ui_base_url, "<path:path>"))
            def swagger_ui_assets(path):
                return static_file(path, SWAGGER_UI_DIR)

    def _swagger_validate(self, callback, route, *args, **kwargs):
        swagger_op = self._swagger_op(route)

        if not swagger_op:

            if not route.rule.startswith(self.swagger_base_path) or self.ignore_undefined_routes:
                return callback(*args, **kwargs)
            elif self.serve_swagger_schema  and route.rule == self.swagger_schema_url:
                return callback(*args, **kwargs)
            elif self.serve_swagger_ui and route.rule.startswith(self.swagger_ui_base_url):
                return callback(*args, **kwargs)
            else:
                return self.swagger_op_not_found_handler(route)

        try:
            request.swagger_op = swagger_op

            try:
                request.swagger_data = self._validate_request(
                    swagger_op, ignore_security_definitions=self.ignore_security_definitions
                )
            except SwaggerSecurityValidationError as e:
                return self.invalid_security_handler(e)
            except ValidationError as e:
                return self.invalid_request_handler(e)

            result = callback(*args, **kwargs)
            result_payload = result.body if isinstance(result, HTTPResponse) else result

            try:
                self._validate_response(swagger_op, result_payload)
            except (ValidationError, MatchingResponseNotFound) as e:
                return self.invalid_response_handler(e)

            if self.auto_jsonify and isinstance(result, (dict, list)):
                result = json_dumps(result)
                response.content_type = 'application/json'
            elif self.auto_jsonify and isinstance(result, HTTPResponse):
                result.body = json_dumps(result_payload)
                response.content_type = result.content_type = 'application/json'
        except Exception as e:
            # Bottle handles redirects by raising an HTTPResponse instance
            if isinstance(e, HTTPResponse):
                raise e

            return self.exception_handler(e)

        return result

    @staticmethod
    def _validate_request(swagger_op, ignore_security_definitions=False):
        if ignore_security_definitions:
            swagger_op = SecurityPatchedOperation(swagger_op)
        return unmarshal_request(BottleIncomingRequest(request), swagger_op)

    @staticmethod
    def _validate_response(swagger_op, result):
        response_spec = get_response_spec(int(response.status_code), swagger_op)
        outgoing_response = BottleOutgoingResponse(response, result)
        validate_response(response_spec, swagger_op, outgoing_response)

    def _swagger_op(self, route):
        # Convert bottle "<param>" style path params to swagger "{param}" style
        path = re.sub(r'/<(.+?)(:.+)?>', r'/{\1}', route.rule)
        return self.swagger.get_op_for_request(request.method, path)

    def _is_swagger_schema_route(self, route):
        return self.serve_swagger_schema and route.rule == self.swagger_schema_suburl


class BottleIncomingRequest(IncomingRequest):
    """
    The Incoming Request wrapper fed into Bravado Core for validation.

    Users should not need to consume this directly.
    """
    def __init__(self, bottle_request):
        self.request = bottle_request
        self.path = bottle_request.url_args

    def json(self):
        return self.request.json

    @property
    def query(self):
        return self.request.query

    @property
    def headers(self):
        return self.request.headers

    @property
    def form(self):
        return self.request.forms

    @property
    def files(self):
        return self.request.files


class BottleOutgoingResponse(OutgoingResponse):
    """
    The Outgoing Response wrapper fed into Bravado Core.

    Users should not need to consume this class directly.
    """
    def __init__(self, bottle_response, response_json):
        self.response = bottle_response
        self.response_json = response_json

    def json(self):
        return self.response_json

    @property
    def content_type(self):
        return self.response.content_type if self.response.content_type else 'application/json'

    @property
    def headers(self):
        return self.response.headers

    @property
    def raw_bytes(self):
        if not self.response.body:
            return b''
        elif isinstance(self.response.body, string_types):
            return self.response.body.encode('utf-8', 'ignore')
        elif isinstance(self.response.body, binary_type):
            return self.response.body
        else:
            # TODO: Unsure if this is quite the correct thing to do.
            return str(self.response.body).encode('utf-8', 'ignore')

    @property
    def text(self):
        if not self.response.body:
            return ''
        elif isinstance(self.response.body, string_types):
            return self.response.body
        elif isinstance(self.response.body, binary_type):
            return self.response.body.decode('utf-8', 'ignore')
        else:
            # TODO: Unsure if this is quite the correct thing to do.
            return str(self.response.body)
