from collections import deque
from contextlib import contextmanager

import pytest

from flask_hypergen.context import context, contextlist
from flask_hypergen.examples.app import create_app


class User:
    pk = 1
    id = 1
    is_authenticated = True
    permissions = frozenset()

    def has_perm(self, permission):
        return permission in self.permissions

    def has_perms(self, permissions):
        return set(permissions) <= set(self.permissions)


class Request:
    def __init__(self):
        self.user = User()
        self.session = {}
        self.endpoint = 'tests.endpoint'
        self.view_args = {}
        self.headers = {}

    def get_full_path(self):
        return 'mock'


class HttpResponse:
    pass


def hypergen_context():
    return {
        'into': contextlist('target_id'),
        'ids': set(),
        'event_handler_callbacks': {},
        'commands': deque(),
        'plugins': [],
    }


def mock_hypergen_callback(func):
    func.reverse = lambda *a, **k: '/path/to/cb/'
    return func


@contextmanager
def mock_middleware():
    with context(request=Request(), user=User()):
        yield


@pytest.fixture
def app(tmp_path):
    return create_app(testing=True, database_url=f'sqlite:///{tmp_path / "example.sqlite3"}')


@pytest.fixture
def client(app):
    return app.test_client()
