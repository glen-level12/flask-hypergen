from __future__ import annotations

from collections import deque
from collections.abc import Callable
from contextlib import contextmanager
from datetime import date, datetime
from datetime import time as dt_time
from functools import wraps
import json
from typing import Any

from flask import Blueprint, Response, current_app, has_app_context
from flask import request as flask_request

from flask_hypergen.context import c, context, context_init_app, contextlist
import flask_hypergen.hypergen as hypergen_mod
from flask_hypergen.hypergen import (
    ResolverMatch,
    check_perms,
    compare_funcs,
    metastr,
    resolve_url,
    route_register,
    t,
    wrap2,
)
from flask_hypergen.template import (
    FULL,
    a,
    base_element,
    hypergen,
    input_,
    join_html,
    raw,
    script,
    select,
)


__all__ = sorted(
    [
        'ASSETS_BLUEPRINT',
        'ActionPlugin',
        'COERCE',
        'EVENT',
        'JS_COERCE_FUNCS',
        'JS_VALUE_FUNCS',
        'LOGIN_REQUIRED',
        'LiveviewPlugin',
        'NO_PERM_REQUIRED',
        'THIS',
        'action',
        'call_js',
        'callback',
        'command',
        'decoder',
        'dumps',
        'encoder',
        'init_app',
        'json_commands_response',
        'liveview',
        'loads',
        'url_is_active',
    ],
)


class THIS:
    pass


class EVENT:
    pass


LOGIN_REQUIRED = '__LOGIN_REQUIRED__'
NO_PERM_REQUIRED = '__NO_PERM_REQUIRED__'
COERCE = {str: 'hypergen.coerce.str', int: 'hypergen.coerce.int', float: 'hypergen.coerce.float'}
JS_VALUE_FUNCS = {
    'checkbox': 'hypergen.read.checked',
    'radio': 'hypergen.read.radio',
    'file': 'hypergen.read.file',
}
JS_COERCE_FUNCS = {
    'month': 'hypergen.coerce.month',
    'number': 'hypergen.coerce.int',
    'range': 'hypergen.coerce.float',
    'week': 'hypergen.coerce.week',
    'date': 'hypergen.coerce.date',
    'time': 'hypergen.coerce.time',
}
JS_COERCE_FUNCS['datetime-local'] = 'hypergen.coerce.datetime'
ASSETS_BLUEPRINT = Blueprint(
    'flask_hypergen',
    __name__,
    static_folder='static',
    static_url_path='/flask_hypergen/static',
)


def init_app(app: Any) -> Any:
    context_init_app(app)
    if ASSETS_BLUEPRINT.name not in app.blueprints:
        app.register_blueprint(ASSETS_BLUEPRINT)
    app.extensions['flask_hypergen'] = True
    return app


def _request_header(request: Any, key: str) -> Any:
    if hasattr(request, 'headers'):
        value = request.headers.get(key)
        if value:
            return value
    meta = getattr(request, 'META', {})
    env_key = f'HTTP_{key.upper().replace("-", "_")}'
    if env_key in meta:
        return meta[env_key]
    environ = getattr(request, 'environ', {})
    return environ.get(env_key)


def _request_path(request: Any) -> str:
    if hasattr(request, 'full_path'):
        return request.full_path.rstrip('?')
    if hasattr(request, 'get_full_path'):
        return request.get_full_path()
    return getattr(request, 'path', '/')


def _static_hypergen_path() -> str:
    if has_app_context() and 'flask_hypergen' in current_app.blueprints:
        return ASSETS_BLUEPRINT.static_url_path + '/hypergen.js'
    return '/flask_hypergen/static/hypergen.js'


def liveview_resolver_match(for_action: bool = False) -> ResolverMatch | None:
    if not for_action:
        endpoint = getattr(c.request, 'endpoint', None)
        kwargs = getattr(c.request, 'view_args', {}) or {}
        return ResolverMatch(func=hypergen_mod._ENDPOINTS.get(endpoint), kwargs=kwargs)
    for header in ['X-Pathname', 'Referer']:
        value = _request_header(c.request, header)
        if value:
            return resolve_url(value)
    return None


def url_is_active(url: str) -> bool:
    current = context.hypergen.liveview_resolver_match
    target = resolve_url(url)
    return current and target and current.func is target.func


def callback_redirect_response(response: Response) -> Response:
    return json_commands_response(
        [['hypergen.redirect', response.location]],
        status=response.status_code,
    )


def namespace_resolve(func: Callable[..., Any]) -> str:
    return getattr(func, 'hypergen_endpoint', getattr(func, '__name__', 'hypergen'))


class LiveviewPluginBase:
    @contextmanager
    def wrap_element_init(
        self,
        element: base_element,
        children: list[Any],
        attrs: dict[str, Any],
    ):
        coerce_to = attrs.pop('coerce_to', None)
        if coerce_to is not None:
            try:
                element.js_coerce_func = COERCE[coerce_to]
            except KeyError as exc:
                raise Exception(f'coerce must be one of: {list(COERCE.keys())}') from exc
        else:
            element.js_coerce_func = attrs.pop('js_coerce_func', None)
        if isinstance(element, input_):
            element.js_value_func = attrs.pop(
                'js_value_func',
                JS_VALUE_FUNCS.get(attrs.get('type_', 'text'), 'hypergen.read.value'),
            )
            if not element.js_coerce_func:
                element.js_coerce_func = JS_COERCE_FUNCS.get(attrs.get('type_', 'text'))
        elif isinstance(element, select):
            if attrs.get('multiple') is True:
                element.js_value_func = attrs.pop('js_value_func', 'hypergen.read.selectMultiple')
                if coerce_to is str:
                    pass
                elif coerce_to is int:
                    element.js_coerce_func = 'hypergen.coerce.intlist'
                else:
                    raise Exception(
                        f'coerce_to={coerce_to} not yet implemented for multiple selects',
                    )
            else:
                element.js_value_func = attrs.pop('js_value_func', 'hypergen.read.value')
        else:
            element.js_value_func = attrs.pop(
                'js_value_func',
                'hypergen.read.contenteditable'
                if attrs.get('contenteditable', False) is True
                else 'hypergen.read.value',
            )
        if isinstance(element, a) and attrs.get('target') in (None, '_self'):
            href = attrs.get('href')
            partial = attrs.pop('partial', True)
            if partial and type(href) is metastr:
                base_template1 = href.meta.get('base_template')
                if base_template1 is not None:
                    base_template2 = c.hypergen.get('partial_base_template')
                    if base_template2 is not None and compare_funcs(base_template1, base_template2):
                        attrs['onclick'] = f"hypergen.partialLoad(event, '{href}', true)"
        yield


class LiveviewPlugin(LiveviewPluginBase):
    @contextmanager
    def context(self):
        with c(at='hypergen', event_handler_callbacks={}, commands=deque()):
            yield

    def process_html(self, html_output):
        def template() -> None:
            raw('<!--hypergen_liveview_media-->')
            script(src=_static_hypergen_path())
            script(
                dumps(c.hypergen.commands),
                type_='application/json',
                id_='hypergen-apply-commands-data',
            )
            script(
                """
                hypergen.ready(() => hypergen.applyCommands(JSON.parse(document.getElementById(
                    'hypergen-apply-commands-data').textContent, hypergen.reviver)))
            """,
            )

        command(
            'hypergen.setClientState',
            'hypergen.eventHandlerCallbacks',
            c.hypergen.event_handler_callbacks,
        )
        path = _request_path(c.request)
        command('history.replaceState', {'callback_url': path}, '', path)
        if '<head>' in html_output:
            assert html_output.count('<head>') == 1, (
                'Ooops, multiple <head> tags found. There can be only one!'
            )
            return html_output.replace('<head>', '<head>' + hypergen(template))
        if '<html>' in html_output:
            assert html_output.count('<html>') == 1, (
                'Ooops, multiple <html> tags found. There can be only one!'
            )
            return html_output.replace('<html>', '<html><head>' + hypergen(template) + '</head>')
        return hypergen(template) + html_output


class ActionPlugin(LiveviewPluginBase):
    def __init__(
        self,
        target_id: str | None = None,
        base_view: Callable[..., Any] | None = None,
        morph: bool = True,
        prepend_commands: bool = True,
    ) -> None:
        self.target_id = target_id
        self.base_view = base_view
        self.morph = morph
        self.prepend_commands = prepend_commands

    @contextmanager
    def context(self):
        with c(
            at='hypergen',
            event_handler_callbacks={},
            commands=deque(),
            target_id=self.target_id,
        ):
            yield

    def template_after(self, **kwargs: Any) -> None:
        extra_target_contexts = {}
        if self.base_view:
            referer_resolver_match = liveview_resolver_match(for_action=True)
            if referer_resolver_match is not None and referer_resolver_match.func is not None:
                isolated_into = contextlist('target_id')
                with c(at='hypergen', ids=set(), into=isolated_into, target_id=None):
                    self.base_view.original_func(
                        c.request,
                        *referer_resolver_match.args,
                        **referer_resolver_match.kwargs,
                    )
                extra_target_contexts = {
                    key: value
                    for key, value in isolated_into.contexts.items()
                    if key != '__default_context__' and value
                }
        commands = [
            [
                'hypergen.setClientState',
                'hypergen.eventHandlerCallbacks',
                c.hypergen.event_handler_callbacks,
            ],
        ]
        if self.morph and 'into' in c.hypergen:
            target_contexts = dict(c.hypergen.into.contexts)
            target_contexts.update(extra_target_contexts)
            for target_id, into in target_contexts.items():
                if into:
                    commands.append(['hypergen.morph', target_id, join_html(into)])
        commands.append(['hypergen.onpushstate'])
        if self.prepend_commands:
            c.hypergen.commands.extendleft(reversed(commands))
        else:
            c.hypergen.commands.extend(commands)


def command(javascript_func_path: str, *args: Any, **kwargs: Any):
    prepend = kwargs.pop('prepend', False)
    return_ = kwargs.pop('return_', False)
    item = [javascript_func_path, *args]
    if return_:
        return item
    if prepend:
        c.hypergen.commands.appendleft(item)
    else:
        c.hypergen.commands.append(item)


def callback(
    url: Any,
    *cb_args: Any,
    debounce: int = 0,
    confirm_: bool = False,
    confirm: bool = False,
    blocks: bool = False,
    upload_files: bool = False,
    clear: bool = False,
    headers: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    when: Any = None,
    each_url_blocks: bool = True,
    timeout: int = 20000,
):
    meta = meta or {}
    headers = headers or {}
    if confirm is not False:
        confirm_ = confirm
    assert getattr(url, 'is_hypergen_liveview', False) is not True, (
        "You can't callback to a @liveview, only an @action."
    )
    if getattr(url, 'supports_hypergen_callback', False) is True:
        url = url.reverse()

    def to_html(element: base_element, key: str, value: Any):
        def fix_this(x: Any) -> Any:
            return element if x is THIS else x

        element.ensure_id()
        cmd = command(
            'hypergen.callback',
            url,
            [fix_this(x) for x in cb_args],
            {
                'debounce': debounce,
                'confirm_': confirm_,
                'blocks': blocks,
                'uploadFiles': upload_files,
                'clear': clear,
                'elementId': element.attrs['id_'],
                'debug': current_app.debug if has_app_context() else False,
                'meta': meta,
                'headers': headers,
                'eachUrlBlocks': each_url_blocks,
                'timeout': timeout,
            },
            return_=True,
        )
        cmd_id = f'{element.attrs["id_"]}__{key}'
        c.hypergen.event_handler_callbacks[cmd_id] = cmd
        when_str = ', ' + dumps(when).replace('"', "'") if when else ''
        return [' ', t(key), '="', f"hypergen.event(event, '{cmd_id}'{when_str})", '"']

    signature = {
        key: value
        for key, value in {
            'debounce': debounce,
            'confirm_': confirm_,
            'blocks': blocks,
            'upload_files': upload_files,
            'clear': clear,
            'meta': meta,
            'when': when,
            'eachUrlBlocks': each_url_blocks,
            'timeout': timeout,
        }.items()
        if value
    }
    to_html.hypergen_callback_signature = 'callback', (url, *cb_args), signature
    return to_html


def call_js(command_path: str, *cb_args: Any):
    def to_html(element: base_element, key: str, value: Any):
        def fix_this(x: Any) -> Any:
            return element if x is THIS else x

        element.ensure_id()
        cmd = command(command_path, *[fix_this(x) for x in cb_args], return_=True)
        cmd_id = f'{element.attrs["id_"]}__{key}'
        c.hypergen.event_handler_callbacks[cmd_id] = cmd
        return [' ', t(key), '="', f"hypergen.event(event, '{cmd_id}')", '"']

    return to_html


def json_commands_response(commands: Any, status: int = 200) -> Response:
    return Response(dumps(commands), status=status, mimetype='application/json')


def _is_redirect_response(response: Any) -> bool:
    return (
        isinstance(response, Response) and 300 <= response.status_code < 400 and response.location
    )


@wrap2
def liveview(
    func,
    router=None,
    rule=None,
    base_template=None,
    perm=None,
    any_perm=False,
    login_url=None,
    raise_exception=False,
    redirect_field_name=None,
    endpoint=None,
    methods=None,
    partial=True,
    target_id=None,
    appstate=None,
    user_plugins=None,
):
    if perm != NO_PERM_REQUIRED:
        assert perm, 'perm is a required keyword argument'
    if target_id is None:
        target_id = getattr(base_template, 'target_id', None)
    if base_template and partial and not target_id:
        raise Exception(f'{func}: Partial loading requires a target_id.')
    partial_base_template = base_template if partial else None
    original_func = func
    user_plugins = user_plugins or []

    @wraps(func)
    def _(*args, **kwargs):
        request = flask_request
        perm_check = check_perms(
            request,
            perm,
            login_url=login_url,
            raise_exception=raise_exception,
            any_perm=any_perm,
            redirect_field_name=redirect_field_name,
        )
        if not perm_check.ok:
            return perm_check.response
        if partial and _request_header(request, 'X-Hypergen-Partial') == '1':
            with c(
                at='hypergen',
                matched_perms=perm_check.matched_perms,
                partial_base_template=partial_base_template,
                liveview_resolver_match=liveview_resolver_match(),
            ):
                full = hypergen(
                    func,
                    request,
                    *args,
                    **kwargs,
                    settings={
                        'action': True,
                        'returns': FULL,
                        'target_id': target_id,
                        'appstate': appstate,
                        'namespace': namespace_resolve(_),
                        'prepend_commands': False,
                        'user_plugins': user_plugins,
                    },
                )
                if _is_redirect_response(full['template_result']):
                    return callback_redirect_response(full['template_result'])
                return json_commands_response(full['context'].hypergen.commands)
        with c(
            at='hypergen',
            matched_perms=perm_check.matched_perms,
            partial_base_template=partial_base_template,
            liveview_resolver_match=liveview_resolver_match(),
        ):
            full = hypergen(
                func,
                request,
                *args,
                **kwargs,
                settings={
                    'liveview': True,
                    'returns': FULL,
                    'base_template': base_template,
                    'appstate': appstate,
                    'namespace': namespace_resolve(_),
                    'user_plugins': user_plugins,
                },
            )
            if isinstance(full['template_result'], Response):
                return full['template_result']
            return Response(full['html'], mimetype='text/html')

    _.original_func = original_func
    _.is_hypergen_liveview = True
    route_register(
        router,
        _,
        rule=rule,
        methods=methods or (['GET', 'POST'] if partial else ['GET']),
        endpoint=endpoint,
        base_template=base_template,
    )
    return _


@wrap2
def action(
    func,
    router=None,
    rule=None,
    base_template=None,
    target_id=None,
    perm=None,
    any_perm=False,
    login_url=None,
    raise_exception=False,
    redirect_field_name=None,
    endpoint=None,
    methods=None,
    partial=True,
    base_view=None,
    appstate=None,
    user_plugins=None,
):
    if perm != NO_PERM_REQUIRED:
        assert perm, 'perm is a required keyword argument'
    if target_id is None:
        target_id = getattr(base_template, 'target_id', None)
    if base_template and partial and not target_id:
        raise Exception(f'{func}: Partial loading requires a target_id.')
    partial_base_template = base_template if partial else None
    user_plugins = user_plugins or []

    @wraps(func)
    def _(*args, **kwargs):
        request = flask_request
        perm_check = check_perms(
            request,
            perm,
            login_url=login_url,
            raise_exception=raise_exception,
            any_perm=any_perm,
            redirect_field_name=redirect_field_name,
        )
        if not perm_check.ok:
            if _is_redirect_response(perm_check.response):
                return callback_redirect_response(perm_check.response)
            return perm_check.response or Response(status=403)
        action_args = loads(request.form['hypergen_data'])['args']
        with c(
            at='hypergen',
            matched_perms=perm_check.matched_perms,
            partial_base_template=partial_base_template,
            liveview_resolver_match=liveview_resolver_match(for_action=True),
        ):
            full = hypergen(
                func,
                request,
                *action_args,
                **kwargs,
                settings={
                    'action': True,
                    'returns': FULL,
                    'target_id': target_id,
                    'appstate': appstate,
                    'namespace': namespace_resolve(_),
                    'base_view': base_view,
                    'user_plugins': user_plugins,
                },
            )
            if _is_redirect_response(full['template_result']):
                return callback_redirect_response(full['template_result'])
            if isinstance(full['template_result'], Response):
                return full['template_result']
            if type(full['template_result']) is list:
                return json_commands_response(full['template_result'])
            return json_commands_response(full['context'].hypergen.commands)

    _.supports_hypergen_callback = True
    route_register(
        router,
        _,
        rule=rule,
        methods=methods or ['POST'],
        endpoint=endpoint,
        base_template=base_template,
    )
    return _


ENCODINGS = {
    date: lambda o: {'_': ['date', str(o)]},
    datetime: lambda o: {'_': ['datetime', str(o)]},
    tuple: lambda o: {'_': ['tuple', list(o)]},
    deque: lambda o: {'_': ['deque', list(o)]},
    set: lambda o: {'_': ['set', list(o)]},
    frozenset: lambda o: {'_': ['frozenset', list(o)]},
    range: lambda o: {'_': ['range', [o.start, o.stop, o.step]]},
    type(EVENT): lambda o: {'_': ['EVENT', None]},
}


def encoder(o):
    if issubclass(type(o), base_element):
        assert o.attrs.get('id_', False), 'Missing id_'
        return ['_', 'element_value', [o.js_value_func, o.js_coerce_func, o.attrs['id_']]]
    fn = ENCODINGS.get(type(o))
    if fn:
        return fn(o)
    raise TypeError(f'{o!r} is not JSON serializable')


DECODINGS = {
    'float': float,
    'date': date.fromisoformat,
    'datetime': datetime.fromisoformat,
    'time': dt_time.fromisoformat,
    'tuple': tuple,
    'deque': deque,
    'set': set,
    'frozenset': frozenset,
    'range': lambda v: range(*v),
}


def decoder(o):
    data = o.get('_', None)
    if data is None or type(data) is not list or len(data) != 2:
        return o
    datatype, value = data
    fn = DECODINGS.get(datatype)
    if fn:
        return fn(value)
    raise Exception(f'Unknown datatype, {datatype}')


def dumps(data, default=encoder, indent=None):
    return json.dumps(data, default=default, separators=(',', ':'), indent=indent)


def loads(data, integer_keys=False):
    def integer_keys_object_pairs_hook(pairs):
        return decoder({int(k) if k.isdigit() else k: v for k, v in pairs})

    if integer_keys is True:
        return json.loads(data, object_pairs_hook=integer_keys_object_pairs_hook)
    return json.loads(data, object_hook=decoder)
