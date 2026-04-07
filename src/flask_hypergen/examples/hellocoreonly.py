# ruff: noqa: F403, F405

from flask import Blueprint, Response, request

from flask_hypergen import *
from flask_hypergen.examples.common import counter_fragment, make_base_template


bp = Blueprint('hellocoreonly', __name__, url_prefix='/hellocoreonly')
BASE_TEMPLATE = make_base_template('Hello Core Only')


def counter_template(n):
    h2('Core-only wiring')
    p('This example uses explicit Flask routes with function-based callback reverse wiring.')
    counter_fragment(n, callback(increment, n))


@bp.get('/counter')
def counter():
    return Response(
        hypergen(counter_template, 0, settings={'liveview': True, 'base_template': BASE_TEMPLATE}),
        mimetype='text/html',
    )


@bp.post('/increment')
def increment():
    n = loads(request.form['hypergen_data'])['args'][0]
    commands = hypergen(
        counter_template,
        n + 1,
        settings={'action': True, 'returns': COMMANDS, 'target_id': 'content'},
    )
    return json_commands_response(commands)


route_register(None, counter, endpoint='hellocoreonly.counter', base_template=BASE_TEMPLATE)
route_register(None, increment, endpoint='hellocoreonly.increment', methods=['POST'])
