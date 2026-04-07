from __future__ import annotations

from flask import Blueprint

from flask_hypergen import NO_PERM_REQUIRED, action, callback, liveview
from flask_hypergen.examples.common import make_base_template
from flask_hypergen.tags import button, h2, p


bp = Blueprint('apptemplate', __name__, url_prefix='/apptemplate')
BASE_TEMPLATE = make_base_template('App Template')


def page_template(n: int) -> None:
    h2('Context-manager base template')
    p('This page demonstrates partial updates against a shared app shell.')
    p(f'Current value: {n}', id_='value')
    button('Increment', id_='app-increment', onclick=callback(increment, n))


@liveview(bp, '/counter', perm=NO_PERM_REQUIRED, base_template=BASE_TEMPLATE)
def counter(request) -> None:
    page_template(0)


@action(bp, '/increment', perm=NO_PERM_REQUIRED, target_id='content', base_view=counter)
def increment(request, n: int) -> None:
    page_template(n + 1)
