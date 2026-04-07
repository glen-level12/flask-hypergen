from __future__ import annotations

from flask import Blueprint

from flask_hypergen import NO_PERM_REQUIRED, action, callback, h2, liveview, p
from flask_hypergen.examples.common import counter_fragment, make_base_template


bp = Blueprint('hellohypergen', __name__, url_prefix='/hellohypergen')
BASE_TEMPLATE = make_base_template('Hello Hypergen')


def counter_template(n: int) -> None:
    h2('Decorator wiring')
    p('This example preserves the django-hypergen liveview/action/callback API names.')
    counter_fragment(n, callback(increment, n))


@liveview(bp, '/counter', perm=NO_PERM_REQUIRED, base_template=BASE_TEMPLATE)
def counter(request) -> None:
    counter_template(0)


@action(bp, '/increment', perm=NO_PERM_REQUIRED, target_id='content', base_view=counter)
def increment(request, n: int) -> None:
    counter_template(n + 1)
