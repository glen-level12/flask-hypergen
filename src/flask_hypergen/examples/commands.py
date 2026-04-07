# ruff: noqa: F403, F405

from flask import Blueprint

from flask_hypergen import *
from flask_hypergen.examples.common import make_base_template


bp = Blueprint('commands', __name__, url_prefix='/commands')
BASE_TEMPLATE = make_base_template('Commands')


def commands_template(message='Ready'):
    h2('Explicit command responses')
    p(message, id_='message')
    div(button('Send command', id_='send-command', onclick=callback(send_command)), class_='stack')


@liveview(bp, '/demo', perm=NO_PERM_REQUIRED, base_template=BASE_TEMPLATE)
def demo(request):
    commands_template()


@action(bp, '/send-command', perm=NO_PERM_REQUIRED)
def send_command(request):
    return [
        command(
            'hypergen.morph',
            'message',
            '<p id="message">Updated from an explicit command.</p>',
            return_=True,
        ),
        command('hypergen.onpushstate', return_=True),
    ]
