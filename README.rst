=====================
Bottle Swagger Plugin
=====================

.. image:: https://travis-ci.org/cope-systems/bottle-swagger.svg?branch=master
    :target: https://travis-ci.org/cope-systems/bottle-swagger

About
-----
This project is a Bottle plugin for working with Swagger.
`Bottle <http://bottlepy.org/>`_ is a Python web framework.
`Swagger (OpenAPI) <http://swagger.io/>`_ is a standard for defining REST APIs.

This plugin is derived from Charles Blaxland's bottle-swagger plugin:
https://github.com/ampedandwired/bottle-swagger

So if you are serving a REST API with Bottle,
and you have a defined a Swagger schema for that API,
this plugin can:

* Validate incoming requests and outgoing responses against the swagger schema
* Return appropriate error responses on validation failures
* Serve your swagger schema via Bottle (for use in `Swagger UI <http://swagger.io/swagger-ui/>`_ for example)

Requirements
------------

* Python >= 2.7
* Bottle >= 0.12
* Swagger specification == 2.0

This project relies on `bravado-core <https://github.com/Yelp/bravado-core>`_ to perform the swagger schema validation,
so any version of the Swagger spec supported by that project is also supported by this plugin. Note that Bravado Core
does not yet support the OpenAPI 3.0 specification, thus this plugin does not work with OpenAPI 3.0 yet.

Installation
------------
::

  $ pip install bottle-swagger-2

Usage
-----
See the "example" directory for a working example of using this plugin.

The simplest usage is::

  import bottle

  swagger_def = _load_swagger_def()
  bottle.install(SwaggerPlugin(swagger_def))

Where "_load_swagger_def" returns a dict representing your swagger specification
(loaded from a yaml file, for example).

There are a number of arguments that you can pass to the plugin constructor:

* ``validate_swagger_spec`` - Boolean (default ``True``) indicating if the plugin should actually validate the Swagger spec.

* ``validate_requests`` - Boolean (default ``True``) indicating if incoming requests should be validated or not.

* ``validate_responses`` - Boolean (default ``True``) indicating if outgoing responses should be validated or not.

* ``use_bravado_models`` - Boolean (default ``True``) Should the Swagger data attached to the request be a Bravado model or just a dictionary?

* ``user_defined_formats`` - List (default ``None``) Any user defined Swagger formats that may be fed into Bravado core.

* ``include_missing_properties`` - Boolean (default ``True``) Should missing properties off of object in Swagger be included with ``None`` values?

* ``default_type_to_object`` - Boolean (default ``False``) Should Swagger attributes or schemas missing the type parameter be forced to be ``object`` by default (if true) or can they be anything (if false).

* ``internally_derefence_refs`` - Boolean (default ``False``) Should Bravado Core dereference all $refs for a performance speedup?

* ``ignore_undefined_api_routes`` - Boolean (default ``False``) Should any routes under the given base path that don't have a Swagger route automatically trigger a 404?

* ``auto_jsonify`` - Boolean (default ``False``) If the Swagger route handlers return a list or dict, should we attempt to automatically convert them to a JSON response?

* ``invalid_request_handler`` - Callback called when request validation has failed. Default behaviour is to return a "400 Bad Request" response.

* ``invalid_response_handler`` - Callback called when response validation has failed. Default behaviour is to return a "500 Server Error" response.

* ``swagger_op_not_found_handler`` - Callback called when no swagger operation matching the request was found in the swagger schema. Default behaviour is to return a "404 Not Found" response.

* ``exception_handler=_server_error_handler`` - Callback called when an exception is thrown by downstream handlers (including exceptions thrown by your code). Default behaviour is to return a "500 Server Error" response.

* ``swagger_base_path`` - String (default ``None``) Used to set and override the ``basePath`` mechanic for telling bottle what subpath to serve the API from.

* ``adjust_api_base_path`` - Boolean (default ``True``) Adjust the basePath reported by the swagger.json. This is important if your WSGI application is running under a subpath.

* ``serve_swagger_schema`` - Boolean (default ``True``) indicating if the Swagger schema JSON should be served

* ``swagger_schema_suburl`` - URL (default ``"/swagger.json"``) on which to serve the Swagger schema JSON from the API subpath

* ``serve_swagger_ui`` - Boolean (default ``False``) Should we use a built-in copy of Swagger UI to serve up docs for this API?

* ``swagger_ui_suburl`` - String (default ``"/ui/"``) The API suburl to serve the built-in Swagger UI up at, if turned on.

* ``swagger_ui_validator_url`` -- String (default ``None``) The URL for a Swagger spec validator. By default this is None (i.e. off).

* ``extra_bravado_config`` - Dict (default ``None``) Any additional configuration items to pass to Bravado core.

All the callbacks above receive a single parameter representing the ``Exception`` that was raised,
or in the case of ``swagger_op_not_found_handler`` the ``Route`` that was not found.
They should all return a Bottle ``Response`` object.

Contributing
------------
Development happens in the `bottle-swagger GitHub respository <https://github.com/cope-systems/bottle-swagger>`_.
Pull requests (with accompanying unit tests), feature suggestions and bug reports are welcome.

Use "tox" to run the unit tests::

  $ tox
