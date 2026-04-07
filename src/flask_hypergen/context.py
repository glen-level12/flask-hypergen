from collections import UserList, defaultdict
from contextlib import contextmanager
import threading

from flask import request as flask_request
from pyrsistent import m, pmap


d = dict


__all__ = [
    'Context',
    'ContextMiddleware',
    'c',
    'context',
    'context_init_app',
    'context_middleware',
    'contextlist',
]


class Context(threading.local):
    def __init__(self):
        self.ctx = pmap()
        super().__init__()

    def replace(self, **items):
        self.ctx = m(**items)

    def __getattr__(self, key):
        try:
            return self.__dict__['ctx'][key]
        except KeyError as exc:
            raise AttributeError(f'No such attribute: {key}') from exc

    def __setattr__(self, key, value):
        if key == 'ctx':
            return super().__setattr__(key, value)
        self.ctx = self.ctx.set(key, value)

    def __getitem__(self, key):
        return self.__dict__['ctx'][key]

    def __setitem__(self, key, value):
        raise Exception('TODO')

    def __contains__(self, key):
        return key in self.ctx

    def clone(self):
        clone = Context()
        clone.ctx = self.ctx
        return clone

    @contextmanager
    def __call__(self, transformer=None, at=None, **items):
        previous = self.ctx
        try:
            if at is None:
                if transformer is not None:
                    self.ctx = transformer(self.ctx)
                self.ctx = self.ctx.update(m(**items))
            else:
                if at not in self.ctx:
                    self.ctx = self.ctx.set(at, pmap(items))
                else:
                    new_value_at = self.ctx[at].update(pmap(items))
                    if not new_value_at:
                        raise Exception(
                            'Not immutable context variable attempted updated. If you want to '
                            'nest with context() statements you must use a pmap() or another '
                            'immutable hashmap type.',
                        )
                    self.ctx = self.ctx.set(at, new_value_at)
                if transformer is not None:
                    self.ctx = self.ctx.set(at, transformer(self.ctx[at]))
            yield
        finally:
            self.ctx = previous


context = Context()
c = context


def _init_context(request):
    values = {'request': request}
    user = getattr(request, 'user', None)
    if user is not None:
        values['user'] = user
    return values


def context_middleware(get_response):
    def _(request):
        with context(**_init_context(request)):
            return get_response(request)

    return _


class ContextMiddleware:
    def process_request(self, request):
        context.replace(**_init_context(request))


def context_init_app(app):
    if app.extensions.get('flask_hypergen_context_init'):
        return

    @app.before_request
    def _context_before_request():
        context.replace(**_init_context(flask_request))

    @app.teardown_request
    def _context_teardown_request(_exc):
        context.replace()

    app.extensions['flask_hypergen_context_init'] = True


class contextlist(UserList):
    def __init__(self, context_key, *args, **kwargs):
        self.context_key = context_key
        self.contexts = defaultdict(list)
        super().__init__(*args, **kwargs)

    def _get_context_value(self):
        if 'hypergen' not in context:
            return '__default_context__'
        target_id = context.hypergen.get(self.context_key, None)
        return target_id if target_id else '__default_context__'

    @property
    def data(self):
        return self.contexts[self._get_context_value()]

    @data.setter
    def data(self, value):
        self.contexts[self._get_context_value()] = value
