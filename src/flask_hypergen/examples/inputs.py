from __future__ import annotations

from flask import Blueprint

from flask_hypergen import NO_PERM_REQUIRED, action, callback, liveview
from flask_hypergen.examples.common import make_base_template
from flask_hypergen.tags import button, div, h2, input_, label, p, span


bp = Blueprint('inputs', __name__, url_prefix='/inputs')
BASE_TEMPLATE = make_base_template('Inputs')


def summary_template(name: str = '', age: int = 0, subscribed: bool = False) -> None:
    h2('Read values from the browser')
    with div(class_='stack'):
        name_input = input_(id_='name', placeholder='Name', value=name)
        age_input = input_(id_='age', type_='number', value=age, coerce_to=int)
        subscribed_input = input_(id_='subscribed', type_='checkbox', checked=subscribed)
        label(subscribed_input, 'Subscribed')
        button(
            'Submit',
            id_='submit',
            onclick=callback(submit, name_input, age_input, subscribed_input),
        )
    p(id_='summary', sep=' ', end='.')
    if name:
        span(f'{name} is {age} years old and subscribed={subscribed}', id_='summary-text')


@liveview(bp, '/demo', perm=NO_PERM_REQUIRED, base_template=BASE_TEMPLATE)
def demo(request) -> None:
    summary_template()


@action(bp, '/submit', perm=NO_PERM_REQUIRED, target_id='content', base_view=demo)
def submit(request, name: str, age: int, subscribed: bool) -> None:
    summary_template(name, age, subscribed)
