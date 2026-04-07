# ruff: noqa: F403, F405

from flask import Blueprint

from flask_hypergen import *
from flask_hypergen.examples.common import counter_fragment, make_base_template


bp = Blueprint('hellohypergen', __name__, url_prefix='/hellohypergen')
BASE_TEMPLATE = make_base_template('Hello Hypergen')


def counter_template(n):
    h2('Decorator wiring')
    p('This example preserves the django-hypergen liveview/action/callback API names.')
    counter_fragment(n, callback(increment, n))


@liveview(bp, '/counter', perm=NO_PERM_REQUIRED, base_template=BASE_TEMPLATE)
def counter(request):
    counter_template(0)


@action(bp, '/increment', perm=NO_PERM_REQUIRED, target_id='content', base_view=counter)
def increment(request, n):
    counter_template(n + 1)
