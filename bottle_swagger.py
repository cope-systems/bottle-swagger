import re
from bottle import request, response, HTTPResponse, json_loads, json_dumps
from bravado_core.exception import MatchingResponseNotFound
from bravado_core.request import IncomingRequest, unmarshal_request
from bravado_core.response import OutgoingResponse, validate_response, get_response_spec
from bravado_core.spec import Spec
from bravado_core.model import Model
from jsonschema import ValidationError
from six.moves.urllib.parse import urljoin, urlparse


def _error_response(status, e):
    response.status = status
    return {"code": status, "message": str(e)}


def default_server_error_handler(e):
    return _error_response(500, e)


def default_bad_request_handler(e):
    return _error_response(400, e)


def default_not_found_handler(e):
    return _error_response(404, e)


class SwaggerPlugin(object):
    DEFAULT_SWAGGER_SCHEMA_SUBURL = '/swagger.json'

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
                 auto_jsonify=True,
                 invalid_request_handler=default_bad_request_handler,
                 invalid_response_handler=default_server_error_handler,
                 swagger_op_not_found_handler=default_not_found_handler,
                 exception_handler=default_server_error_handler,
                 serve_swagger_schema=True,
                 swagger_base_path=None,
                 swagger_schema_suburl=DEFAULT_SWAGGER_SCHEMA_SUBURL,
                 extra_bravado_config=None):
        """
        Add Swagger validation to your Bottle application.

        :param swagger_def: The raw Swagger 2.0 specification, as a Python dictionary.
        :type swagger_def: dict
        :param validate_swagger_spec: Should plugin validate the given Swagger specification?
        :type: validate_swagger_spec: bool
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
        :param auto_jsonify: Should we automatically convert data returned from our callbacks to JSON? Bottle
            normally will attempt to convert only objects, but we can do better.
        :type auto_jsonify: bool
        :param invalid_request_handler: This handler is triggered when the request validation fails.
        :type invalid_request_handler: str -> HTTP Response
        :param invalid_response_handler: This handler is triggered when the response validation fails.
        :type invalid_response_handler: str -> HTTP Response
        :param swagger_op_not_found_handler: This handler is triggered if the route isn't found for the API subpath,
           and ignore_missing_routes has been set True.
        :type swagger_op_not_found_handler: str -> HTTP Response
        :param exception_handler: This handler is triggered if the request callback threw an exception.
        :type exception_handler: str -> HTTP Response.
        :param serve_swagger_schema: Should we serve the Swagger schema?
        :type serve_swagger_schema: bool
        :param swagger_base_path: Override the base path for the API specified in the swagger spec/
        :type swagger_base_path: str
        :param swagger_schema_suburl: The subpath in the API to serve the swagger schema.
        :type swagger_schema_suburl: str
        :param extra_bravado_config: Any additional Bravado configuration items you may want.
        :type extra_bravado_config: object
        """

        swagger_def = dict(swagger_def)
        if swagger_base_path is not None:
            swagger_def.update(basePath=swagger_base_path)

        self.ignore_undefined_routes = ignore_undefined_api_routes
        self.auto_jsonify = auto_jsonify
        self.invalid_request_handler = invalid_request_handler
        self.invalid_response_handler = invalid_response_handler
        self.swagger_op_not_found_handler = swagger_op_not_found_handler
        self.exception_handler = exception_handler
        self.serve_swagger_schema = serve_swagger_schema

        self.swagger_schema_suburl = swagger_schema_suburl
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

    def apply(self, callback, route):
        def wrapper(*args, **kwargs):
            return self._swagger_validate(callback, route, *args, **kwargs)

        return wrapper

    def setup(self, app):
        if self.serve_swagger_schema:
            @app.get(urljoin(self.swagger_base_path, self.swagger_schema_suburl))
            def swagger_schema():
                return self.swagger.spec_dict

    def _swagger_validate(self, callback, route, *args, **kwargs):
        swagger_op = self._swagger_op(route)

        if not swagger_op:

            if not route.rule.startswith(self.swagger_base_path) or self.ignore_undefined_routes:
                return callback(*args, **kwargs)
            elif self.serve_swagger_schema and route.rule == urljoin(self.swagger_base_path, self.swagger_schema_suburl):
                return callback(*args, **kwargs)
            else:
                return self.swagger_op_not_found_handler(route)

        try:
            request.swagger_op = swagger_op

            try:
                request.swagger_data = self._validate_request(swagger_op)
            except ValidationError as e:
                return self.invalid_request_handler(e)

            result = callback(*args, **kwargs)

            try:
                self._validate_response(swagger_op, result)
            except (ValidationError, MatchingResponseNotFound) as e:
                return self.invalid_response_handler(e)

            if self.auto_jsonify and isinstance(result, (dict, list)):
                result = json_dumps(result)
                response.content_type = 'application/json'
        except Exception as e:
            # Bottle handles redirects by raising an HTTPResponse instance
            if isinstance(e, HTTPResponse):
                raise e

            return self.exception_handler(e)

        return result

    @staticmethod
    def _validate_request(swagger_op):
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


class BottleOutgoingResponse(OutgoingResponse):

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
    def text(self):
        return self.response.status
