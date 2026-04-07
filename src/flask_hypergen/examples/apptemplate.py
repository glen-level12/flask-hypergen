# ruff: noqa: F403, F405

from flask import Blueprint

from flask_hypergen import *
from flask_hypergen.examples.common import make_base_template


bp = Blueprint('apptemplate', __name__, url_prefix='/apptemplate')
BASE_TEMPLATE = make_base_template('App Template')


def page_template(n):
    h2('Context-manager base template')
    p('This page demonstrates partial updates against a shared app shell.')
    p(f'Current value: {n}', id_='value')
    button('Increment', id_='app-increment', onclick=callback(increment, n))


@liveview(bp, '/counter', perm=NO_PERM_REQUIRED, base_template=BASE_TEMPLATE)
def counter(request):
    page_template(0)


@action(bp, '/increment', perm=NO_PERM_REQUIRED, target_id='content', base_view=counter)
def increment(request, n):
    page_template(n + 1)
