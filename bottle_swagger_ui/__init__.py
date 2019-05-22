import os
from bottle import SimpleTemplate

SWAGGER_UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor', 'swagger-ui-3.22.2-dist')
SWAGGER_UI_INDEX_TEMPLATE_PATH = os.path.join(SWAGGER_UI_DIR, 'index.html.st')

with open(SWAGGER_UI_INDEX_TEMPLATE_PATH, 'r') as f:
    SWAGGER_UI_INDEX_TEMPLATE = f.read()


def render_index_html(swagger_spec_url):
    return SimpleTemplate(SWAGGER_UI_INDEX_TEMPLATE).render(swagger_spec_url=swagger_spec_url)
