from unittest import TestCase

from bottle import Bottle, redirect, request
from bottle_swagger import SwaggerPlugin
from webtest import TestApp


class TestBottleSwagger(TestCase):
    VALID_JSON = {"id": "123", "name": "foo"}
    INVALID_JSON = {"not_id": "123", "name": "foo"}

    SWAGGER_DEF = {
        "swagger": "2.0",
        "info": {"version": "1.0.0", "title": "bottle-swagger"},
        "consumes": ["application/json"],
        "produces": ["application/json"],
        "definitions": {
            "Thing": {
                "type": "object",
                "required": ["id"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"}
                }
            }
        },
        "paths": {
            "/thing": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "",
                            "schema": {
                                "$ref": "#/definitions/Thing"
                            }
                        }
                    }
                },
                "post": {
                    "parameters": [{
                        "name": "thing",
                        "in": "body",
                        "required": True,
                        "schema": {
                            "$ref": "#/definitions/Thing"
                        }
                    }],
                    "responses": {
                        "200": {
                            "description": "",
                            "schema": {
                                "$ref": "#/definitions/Thing"
                            }
                        }
                    }
                }
            },
            "/thing/{thing_id}": {
                "get": {
                    "parameters": [{
                        "name": "thing_id",
                        "in": "path",
                        "required": True,
                        "type": "string"
                    }],
                    "responses": {
                        "200": {
                            "description": "",
                            "schema": {
                                "$ref": "#/definitions/Thing"
                            }
                        }
                    }
                }
            },
            "/thing_query": {
                "get": {
                    "parameters": [{
                        "name": "thing_id",
                        "in": "query",
                        "required": True,
                        "type": "string"
                    }],
                    "responses": {
                        "200": {
                            "description": "",
                            "schema": {
                                "$ref": "#/definitions/Thing"
                            }
                        }
                    }
                }
            },
            "/thing_header": {
                "get": {
                    "parameters": [{
                        "name": "thing_id",
                        "in": "header",
                        "required": True,
                        "type": "string"
                    }],
                    "responses": {
                        "200": {
                            "description": "",
                            "schema": {
                                "$ref": "#/definitions/Thing"
                            }
                        }
                    }
                }
            },
            "/thing_formdata": {
                "post": {
                    "consumes": [
                        "application/x-www-form-urlencoded",
                        "multipart/form-data"
                    ],
                    "parameters": [{
                        "name": "thing_id",
                        "in": "formData",
                        "required": True,
                        "type": "string"
                    }],
                    "responses": {
                        "200": {
                            "description": "",
                            "schema": {
                                "$ref": "#/definitions/Thing"
                            }
                        }
                    }
                }
            },
            "/thing_no_resp_body": {
                "post": {
                    "responses": {
                        "200": {
                            "description": "Succeeded."
                        }
                    }
                }
            },
            '/thing_delete': {
                "delete": {
                    "responses": {
                        "200": {
                            "description": "Succeeded."
                        }
                    }
                }
            }
        }
    }

    def check_for_request_addons(self):
        self.assertIsNotNone(getattr(request, 'swagger_data'))
        self.assertIsNotNone(getattr(request, 'swagger_op'))
        return True

    def test_valid_get_request_and_response(self):

        response = self._test_request(extra_check=self.check_for_request_addons)
        self.assertEqual(response.status_int, 200)

    def test_valid_post_request_and_response(self):
        response = self._test_request(method='POST', extra_check=self.check_for_request_addons)
        self.assertEqual(response.status_int, 200)

    def test_invalid_request(self):
        response = self._test_request(method='POST', request_json=self.INVALID_JSON)
        self._assert_error_response(response, 400)

    def test_invalid_response(self):
        response = self._test_request(response_json=self.INVALID_JSON)
        self._assert_error_response(response, 500)

    def test_disable_request_validation(self):
        self._test_disable_validation(validate_requests=False, expected_request_status=200,
                                      expected_response_status=500)

    def test_disable_response_validation(self):
        self._test_disable_validation(validate_responses=False, expected_request_status=400,
                                      expected_response_status=200)

    def test_disable_all_validation(self):
        self._test_disable_validation(validate_requests=False, validate_responses=False, expected_request_status=200,
                                      expected_response_status=200)

    def test_exception_handling(self):
        def throw_ex():
            raise Exception("Exception occurred")

        response = self._test_request(response_json=throw_ex)
        self._assert_error_response(response, 500)

    def test_invalid_route(self):
        response = self._test_request(url="/invalid")
        self._assert_error_response(response, 404)

        response = self._test_request(url="/thing/invalid")
        self._assert_error_response(response, 404)

    def test_ignore_invalid_route(self):
        swagger_plugin = self._make_swagger_plugin(ignore_undefined_api_routes=True)
        response = self._test_request(swagger_plugin=swagger_plugin, url="/invalid")
        self.assertEqual(response.status_int, 200)
        response = self._test_request(swagger_plugin=swagger_plugin, url="/invalid", method='POST',
                                      request_json=self.INVALID_JSON, response_json=self.INVALID_JSON)
        self.assertEqual(response.status_int, 200)

    def test_redirects(self):
        def _test_redirect(swagger_plugin):
            def redir():
                redirect("/actual_thing")

            response = self._test_request(response_json=redir, swagger_plugin=swagger_plugin)
            self.assertEqual(response.status_int, 302)

        _test_redirect(self._make_swagger_plugin())
        _test_redirect(self._make_swagger_plugin(ignore_undefined_api_routes=True))

    def test_path_parameters(self):
        response = self._test_request(url="/thing/123", route_url="/thing/<thing_id>")
        self.assertEqual(response.status_int, 200)

    def test_path_parameters_regex(self):
        response = self._test_request(url="/thing/123", route_url="/thing/<thing_id:re:[0-9]+>")
        self.assertEqual(response.status_int, 200)

    def test_query_parameters(self):
        response = self._test_request(url="/thing_query?thing_id=123", route_url="/thing_query")
        self.assertEqual(response.status_int, 200)

    def test_header_parameters(self):
        response = self._test_request(url="/thing_header", route_url="/thing_header", headers={'thing_id': '123'})
        self.assertEqual(response.status_int, 200)

    def test_formdata_parameters(self):
        response = self._test_request(
            url="/thing_formdata", route_url="/thing_formdata", method='POST',
            request_json='thing_id=123', content_type='multipart/form-data'
        )
        self.assertEqual(response.status_int, 200)

    def test_get_swagger_schema(self):
        bottle_app = Bottle()
        bottle_app.install(self._make_swagger_plugin())
        test_app = TestApp(bottle_app)
        response = test_app.get(SwaggerPlugin.DEFAULT_SWAGGER_SCHEMA_SUBURL)
        self.assertEqual(response.json, self.SWAGGER_DEF)

    def test_get_swagger_schema_altered_basepath(self):
        bottle_app = Bottle()
        spec_with_basepath = dict(self.SWAGGER_DEF)
        spec_with_basepath['basePath'] = "/api/1.0"
        bottle_app.install(SwaggerPlugin(spec_with_basepath))
        test_app = TestApp(bottle_app)
        response = test_app.get("/api/1.0" + SwaggerPlugin.DEFAULT_SWAGGER_SCHEMA_SUBURL)
        self.assertEqual(response.json, spec_with_basepath)

    def test_get_swagger_ui(self):
        bottle_app = Bottle()
        bottle_app.install(self._make_swagger_plugin(serve_swagger_ui=True))
        test_app = TestApp(bottle_app)
        response = test_app.get("/ui/")
        self.assertEqual(response.status_int, 200)
        for keyword in ["html", "swagger-ui", "/swagger.json"]:
            assert keyword in response.text

    def test_empty_response_body(self):
        response = self._test_request(
            url="/thing_no_resp_body",
            method='POST',
            response_json=''
        )
        self.assertEqual(response.status_int, 200)

        response = self._test_request(
            url="/thing_no_resp_body",
            method='POST',
            response_json='{}'
        )
        self.assertEqual(response.status_int, 200)

        response = self._test_request(
            url="/thing_no_resp_body",
            method='POST',
            response_json=b'{}'
        )
        self.assertEqual(response.status_int, 200)

        response = self._test_request(
            url="/thing_delete",
            method='DELETE',
            response_json=''
        )
        self.assertEqual(response.status_int, 200)

    def test_dont_serve_schema(self):
        bottle_app = Bottle()
        bottle_app.install(self._make_swagger_plugin(
            serve_swagger_ui=False, serve_swagger_schema=False, ignore_undefined_api_routes=True
        ))
        @bottle_app.route("/", "GET")
        def index():
            return "test"
        test_app = TestApp(bottle_app)
        response = test_app.get("/")
        self.assertEqual(response.status_int, 200)

    def _test_request(self, swagger_plugin=None, method='GET', url='/thing', route_url=None, request_json=VALID_JSON,
                      response_json=VALID_JSON, headers=None, content_type='application/json',
                      extra_check=lambda *args, **kwargs: True):
        if swagger_plugin is None:
            swagger_plugin = self._make_swagger_plugin()
        if response_json is None:
            response_json = {}
        if route_url is None:
            route_url = url

        bottle_app = Bottle()
        bottle_app.install(swagger_plugin)

        @bottle_app.route(route_url, method)
        def do_thing(*args, **kwargs):
            extra_check(*args, **kwargs)
            return response_json() if hasattr(response_json, "__call__") else response_json

        test_app = TestApp(bottle_app)
        if method.upper() == 'GET':
            response = test_app.get(url, expect_errors=True, headers=headers)
        elif method.upper() == 'POST':
            if content_type == 'application/json':
                response = test_app.post_json(url, request_json, expect_errors=True, headers=headers)
            else:
                response = test_app.post(
                    url, request_json, content_type=content_type, expect_errors=True, headers=headers
                )
        elif method.upper() == 'DELETE':
            if content_type == 'aplication/json':
                response = test_app.delete_json(
                    url, request_json, expect_errors=True, headers=headers
                )
            else:
                response = test_app.delete(
                    url, request_json, content_type=content_type, expect_errors=True, headers=headers
                )
        else:

            raise Exception("Invalid method {}".format(method))

        return response

    def _test_disable_validation(self, validate_requests=True, validate_responses=True, expected_request_status=200,
                                 expected_response_status=200):
        swagger_plugin = self._make_swagger_plugin(validate_requests=validate_requests,
                                                   validate_responses=validate_responses)

        response = self._test_request(swagger_plugin=swagger_plugin, method='POST', request_json=self.INVALID_JSON)
        self.assertEqual(response.status_int, expected_request_status)

        response = self._test_request(swagger_plugin=swagger_plugin, response_json=self.INVALID_JSON)
        self.assertEqual(response.status_int, expected_response_status)

    def _assert_error_response(self, response, expected_status):
        self.assertEqual(expected_status, response.status_int)
        self.assertEqual(expected_status, response.json['code'])
        self.assertIsNotNone(response.json['message'])

    def _make_swagger_plugin(self, *args, **kwargs):
        return SwaggerPlugin(self.SWAGGER_DEF, *args, **kwargs)
