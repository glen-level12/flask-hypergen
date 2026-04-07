from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from functools import update_wrapper
from html import escape
import inspect
import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from flask import Flask, Response, current_app, redirect, url_for
from werkzeug.exceptions import Forbidden

from flask_hypergen.context import context, user_resolve


logger = logging.getLogger(__name__)

__all__ = [
    'AUTOURL_WSGI_ERR_MSG',
    'ResolverMatch',
    'autourl_register',
    'autourls',
    'check_perms',
    'compare_funcs',
    'is_collection',
    'make_string',
    'metastr',
    'plugins_exit_stack',
    'plugins_method_call',
    'plugins_pipeline',
    'resolve_url',
    'route_register',
    't',
    'wrap2',
]

AUTOURL_WSGI_ERR_MSG = (
    "Hypergen: I'm sorry, I can't auto reverse the url for this liveview/action. "
    'The attribute `hypergen_endpoint` should exist on the wrapped function. '
    'func: {}, module: {}'
)

_URLS = {}
_ENDPOINTS = {}


@dataclass
class ResolverMatch:
    func: object | None
    args: tuple = ()
    kwargs: dict | None = None

    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}


def make_string(value):
    return '' if value is None else str(value)


def t(value, quote=True):
    return escape(make_string(value), quote=quote)


def wrap2(func):
    def _(*args, **kwargs):
        if len(args) == 1 and not kwargs and callable(args[0]):
            wrapped = func(args[0])
            update_wrapper(wrapped, args[0])
            return wrapped

        def f3(f4):
            wrapped = func(f4, *args, **kwargs)
            update_wrapper(wrapped, f4)
            return wrapped

        return f3

    return _


def compare_funcs(a, b):
    return all(
        getattr(a, key) == getattr(b, key)
        for key in ('__doc__', '__name__', '__module__', '__qualname__')
    )


def is_collection(value):
    if type(value) in [str, metastr]:
        return False
    try:
        iter(value)
        return True
    except TypeError:
        return False


def check_perms(
    request,
    perm,
    login_url=None,
    raise_exception=False,
    any_perm=False,
    redirect_field_name=None,
):
    from flask_hypergen.liveview import LOGIN_REQUIRED, NO_PERM_REQUIRED

    matched_perms = set()
    if perm == NO_PERM_REQUIRED:
        return True, None, matched_perms
    assert perm, 'perm= is required'

    def auth_failure_response():
        if raise_exception:
            raise Forbidden()
        login_target = login_url
        if login_target is None:
            login_manager = current_app.extensions.get('login_manager')
            login_target = getattr(login_manager, 'login_view', None)
        if not login_target:
            return Response(status=403)
        if not (str(login_target).startswith('/') or '://' in str(login_target)):
            login_target = url_for(login_target)
        redirect_name = redirect_field_name or 'next'
        next_value = getattr(request, 'url', None) or getattr(request, 'path', '/')
        split = urlsplit(login_target)
        query = dict(parse_qsl(split.query, keep_blank_values=True))
        query.setdefault(redirect_name, next_value)
        return redirect(urlunsplit(split._replace(query=urlencode(query))))

    def is_authenticated(user):
        return bool(user and getattr(user, 'is_authenticated', False))

    def has_perm(user, name):
        checker = getattr(user, 'has_perm', None)
        return checker(name) if checker else False

    def has_perms(user, names):
        checker = getattr(user, 'has_perms', None)
        if checker:
            return checker(names)
        return all(has_perm(user, name) for name in names)

    user = user_resolve(request) or getattr(context, 'user', None)
    if perm == LOGIN_REQUIRED:
        if is_authenticated(user):
            return True, None, matched_perms
        return False, auth_failure_response(), matched_perms

    perms = (perm,) if isinstance(perm, str) else tuple(perm)
    if not is_authenticated(user):
        return False, auth_failure_response(), matched_perms
    if any_perm is not True:
        if has_perms(user, perms):
            matched_perms = set(perms)
            return True, None, matched_perms
    else:
        matched_perms = {name for name in perms if has_perm(user, name)}
        if matched_perms:
            return True, None, matched_perms
    if raise_exception:
        raise Forbidden()
    return False, Response(status=403), matched_perms


class metastr(str):
    @staticmethod
    def make(string, meta):
        value = metastr(string)
        value.meta = meta
        return value


def _qualified_endpoint(router, endpoint):
    if router is None or isinstance(router, Flask):
        return endpoint
    return f'{router.name}.{endpoint}'


def _reverse_factory(func, endpoint, base_template=None):
    signature = inspect.signature(getattr(func, 'original_func', func))
    param_names = [name for name in signature.parameters if name != 'request']

    def _reverse(*view_args, **view_kwargs):
        if len(view_args) > len(param_names):
            raise TypeError(f'Too many positional arguments for reverse() on {func.__name__}')
        params = dict(zip(param_names, view_args, strict=False))
        params.update(view_kwargs)
        return metastr.make(url_for(endpoint, **params), {'base_template': base_template})

    _reverse.hypergen_endpoint = endpoint
    return _reverse


def autourl_register(func, base_template=None, path=None, re_path=None):
    module = func.__module__
    _URLS.setdefault(module, set())
    _URLS[module].add((func, path, re_path, base_template))
    return func


def autourls(module, namespace):
    return [item for item in _URLS.get(module.__name__, []) if namespace]


def route_register(router, func, *, rule=None, methods=None, endpoint=None, base_template=None):
    methods = list(methods or ['GET'])
    endpoint = endpoint or func.__name__
    qualified_endpoint = _qualified_endpoint(router, endpoint)
    func.reverse = _reverse_factory(func, qualified_endpoint, base_template=base_template)
    func.hypergen_endpoint = qualified_endpoint
    func.supports_hypergen_callback = any(method.upper() == 'POST' for method in methods)
    _ENDPOINTS[qualified_endpoint] = func
    if router is not None:
        router.add_url_rule(
            rule or f'/{func.__name__}/',
            endpoint,
            func,
            methods=methods,
        )
    return func


def resolve_url(url, method='GET'):
    path = urlsplit(url).path or url
    adapter = current_app.url_map.bind('localhost')
    endpoint, kwargs = adapter.match(path, method=method)
    return ResolverMatch(func=_ENDPOINTS.get(endpoint), kwargs=kwargs)


@contextmanager
def plugins_exit_stack(method_name):
    with ExitStack() as stack:
        for plugin in context.hypergen.plugins:
            if hasattr(plugin, method_name):
                stack.enter_context(plugin.context())
        yield


def plugins_method_call(method_name, *args, **kwargs):
    for plugin in context.hypergen.plugins:
        method = getattr(plugin, method_name, None)
        if method:
            method(*args, **kwargs)


def plugins_pipeline(method_name, data, kwargs=None):
    kwargs = kwargs or {}
    for plugin in context.hypergen.plugins:
        method = getattr(plugin, method_name, None)
        if method:
            data = method(data, **kwargs)
    return data
