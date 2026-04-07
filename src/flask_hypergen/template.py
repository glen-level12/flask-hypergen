# ruff: noqa: F403, F405, SIM117

from collections import OrderedDict
from contextlib import ContextDecorator, ExitStack, contextmanager
from copy import deepcopy
from datetime import datetime
from functools import wraps
from pprint import pformat
from types import GeneratorType

from flask import Response

from flask_hypergen.context import context as c
from flask_hypergen.context import contextlist
from flask_hypergen.hypergen import *
from flask_hypergen.plugins.appstate import AppstatePlugin


try:
    import docutils.core
    import docutils.utils

    docutils_ok = True
except ImportError:
    docutils_ok = False

try:
    from yattag import indent as indent_

    yattag_ok = True
except ImportError:
    yattag_ok = False

OMIT = '__OMIT__'
HTML = 'HTML'
FULL = 'FULL'
COMMANDS = 'COMMANDS'
HYPERGEN_RETURNS = {HTML, FULL, COMMANDS}
DELETED = ''


def add_class(a, b):
    assert type(b) is str, 'b must be string for now. PR?'
    if a in ('', OMIT, None):
        return b
    if type(a) is str:
        return a.strip() + ' ' + b
    if is_collection(a):
        if hasattr(a, 'append'):
            a.append(b)
            return a
        if hasattr(a, 'add'):
            a.add(b)
            return a
        raise Exception('This class collection has neither an append() or add() method. Help!')
    raise Exception("I don't know how to add these variables together in the context of classes.")


def on_url(url, value_on_url=True, value_not_on_url=False):
    from flask_hypergen.liveview import url_is_active

    return value_on_url if url_is_active(url) else value_not_on_url


class TemplatePlugin:
    @contextmanager
    def context(self):
        with c(at='hypergen', into=contextlist('target_id'), ids=set()):
            yield


def hypergen(template, *args, **kwargs):
    assert 'request' in c, "The 'flask_hypergen.context.context_init_app' hook must be installed!"
    settings = kwargs.pop('settings', {})
    plugins = settings.get('plugins', [TemplatePlugin()])
    if settings.get('liveview', False):
        from flask_hypergen.liveview import LiveviewPlugin

        plugins.append(LiveviewPlugin())
    if settings.get('action', False):
        from flask_hypergen.liveview import ActionPlugin

        plugins.append(
            ActionPlugin(
                target_id=settings.get('target_id', None),
                base_view=settings.get('base_view', None),
                prepend_commands=settings.get('prepend_commands', True),
            ),
        )
    if settings.get('appstate', False):
        namespace = getattr(settings['appstate'], 'namespace', settings.get('namespace', None))
        assert namespace, 'When appstate is set, namespace must be too.'
        plugins.append(AppstatePlugin(namespace, settings['appstate']))
    returns = settings.get('returns', HTML)
    assert returns in HYPERGEN_RETURNS, (
        f"The 'returns' hypergen setting must be one of {HYPERGEN_RETURNS!r}"
    )
    indent = settings.get('indent', False)
    base_template = settings.get('base_template', None)
    plugins.extend(settings.get('user_plugins', []))
    with c(at='hypergen', plugins=plugins, base_template=base_template):
        with plugins_exit_stack('context'):
            plugins_method_call('template_before')
            template_result = (base_template()(template) if base_template else template)(
                *args,
                **kwargs,
            )
            plugins_method_call('template_after', template_result=template_result)
            html = join_html(c.hypergen.into) if 'into' in c.hypergen else ''
            html = plugins_pipeline('process_html', html)
            if indent:
                if not yattag_ok:
                    raise Exception("Do 'pip install yattag' to use the indent feature.")
                html = indent_(html, indentation='    ', newline='\n', indent_text=True)
            if returns == HTML:
                return html
            if returns == COMMANDS:
                return c.hypergen.commands
            return {'html': html, 'context': c.clone(), 'template_result': template_result}


def hypergen_to_response(func, *args, **kwargs):
    return Response(hypergen(func, *args, **kwargs), mimetype='text/html')


def join_html(html):
    def fmt(items):
        for item in items:
            if issubclass(type(item), base_element):
                yield item.as_string()
            elif callable(item):
                yield item()
            elif type(item) is GeneratorType:
                with c(at='hypergen', into=[]):
                    yield join_html(item)
            else:
                yield item

    return ''.join(make_string(x) for x in fmt(html))


def raw(*children):
    c.hypergen.into.extend(children)


def write(*children):
    c.hypergen.into.extend(t(x) for x in children)


def rst(restructured_text, report_level=None):
    if not docutils_ok:
        raise Exception("Please 'pip install docutils' to use the rst() function.")
    report_level = report_level or docutils.utils.Reporter.SEVERE_LEVEL + 1
    raw(
        docutils.core.publish_parts(
            restructured_text,
            writer_name='html',
            settings_overrides={'_disable_config': True, 'report_level': report_level},
        )['html_body'],
    )


def hprint(*args, **kwargs):
    @component
    def typeinfo(x):
        span(
            ' (',
            x.__class__.__module__,
            '.',
            type(x).__name__,
            ')',
            style={'color': 'darkgrey'},
        )

    def fmt(x):
        pre(code(pformat(x, width=120)), style={})

    with div(
        style={
            'padding': '8px',
            'margin': '4px 0 0 0',
            'background': '#ffc',
            'color': 'black',
            'font_family': 'sans-serif',
        },
    ):
        if len(args) == 1 and not kwargs:
            div(typeinfo(args[0]))
            fmt(args[0])
        else:
            for i, arg in enumerate(args, 1):
                div(b('arg', i, sep=' '), typeinfo(arg))
                fmt(arg)
        for key, value in kwargs.items():
            div(b(key), typeinfo(value))
            fmt(value)


class base_element(ContextDecorator):
    void = False
    auto_id = False

    def __new__(cls, *args, **kwargs):
        instance = ContextDecorator.__new__(cls)
        instance.tag = cls.__name__.rstrip('_')
        return instance

    def __init__(self, *children, **attrs):
        with ExitStack() as stack:
            children = list(children)
            for plugin in c.hypergen.plugins:
                if hasattr(plugin, 'wrap_element_init'):
                    stack.enter_context(plugin.wrap_element_init(self, children, attrs))
            children = tuple(children)
            assert 'hypergen' in c, 'Element called outside hypergen context.'
            self.t = attrs.pop('t', t)
            self.children = children
            self.attrs = attrs
            self.sep = attrs.pop('sep', '')
            self.end_char = attrs.pop('end', None)
            id_ = self.attrs.get('id_', self.attrs.pop('id', None))
            if type(id_) in (tuple, list):
                id_ = '-'.join(str(x) for x in id_)
            self.attrs['id_'] = id_
            if id_ is not None:
                assert id_ not in c.hypergen['ids'], f'Duplicate id: {id_}'
                c.hypergen['ids'].add(id_)
            self.i = len(c.hypergen.into)
            c.hypergen.into.extend(self.start())
            c.hypergen.into.extend(self.end())
            self.j = len(c.hypergen.into)
            super().__init__()

    def __enter__(self):
        c.hypergen.into.extend(self.start())
        self.delete()
        return self

    def __exit__(self, *exc):
        if not self.void:
            c.hypergen.into.extend(self.end())

    def __repr__(self):
        from flask_hypergen.liveview import THIS

        def value(v):
            if v is THIS:
                return 'THIS'
            if callable(v) and hasattr(v, 'hypergen_callback_signature'):
                name, a, kw = v.hypergen_callback_signature
                return f'{name}({signature(a, kw)})'
            if callable(v):
                if hasattr(v, '__name__'):
                    return '.'.join((v.__module__, v.__name__)).replace('builtins.', '')
                return repr(v)
            if type(v) is str:
                return f'"{v}"'
            return repr(v)

        def signature(a, kw):
            a, kw = deepcopy(a), deepcopy(kw)
            return ', '.join(
                [value(x) for x in a] + [f'{k}={value(v)}' for k, v in kw.items() if v is not None],
            )

        return f'{self.__class__.__name__}({signature(self.children, self.attrs)})'

    def as_string(self):
        into = self.start()
        into.extend(self.end())
        return join_html(into)

    def delete(self):
        for i in range(self.i, self.j):
            c.hypergen.into[i] = DELETED

    def format_children(self, children, nested=False):
        into = []
        sep = self.t(self.sep)
        for x in children:
            if x in ('', None):
                continue
            if issubclass(type(x), base_element):
                x.delete()
                into.append(x)
            elif type(x) is Component:
                x.delete()
                into.extend(x.into)
            elif type(x) in (list, tuple, GeneratorType):
                into.extend(self.format_children(list(x), nested=True))
            elif callable(x):
                into.append(x)
            else:
                into.append(self.t(x))
            if sep:
                into.append(sep)
        if sep and children:
            into.pop()
        if self.end_char and not nested:
            into.append(self.t(self.end_char))
        return into

    def ensure_id(self):
        assert self.attrs['id_'] is not None, (
            f"This element needs an id_='myid' attribute: {self!r}"
        )

    def attribute(self, key, value):
        key = t(key).rstrip('_').replace('_', '-')
        if value == OMIT or value is None:
            return []
        if callable(value):
            return value(self, key, value)
        if type(value) is bool:
            return [' ', key] if value is True else []
        if key == 'style' and type(value) in (dict, OrderedDict):
            return [
                ' ',
                key,
                '="',
                ';'.join(t(k.replace('_', '-')) + ':' + t(v) for k, v in value.items()),
                '"',
            ]
        if key == 'class' and type(value) in (list, tuple, set):
            return [' ', key, '="', t(' '.join(value)), '"']
        value = '' if value is None else t(value)
        assert '"' not in value, 'How dare you put a " in my attributes! :)'
        return [' ', key, '="', value, '"']

    def start(self):
        cache = getattr(self, '_start_cache', None)
        if cache:
            return cache
        into = ['<', self.tag]
        for key, value in self.attrs.items():
            into.extend(self.attribute(key, value))
        if self.void:
            into.append('/')
        into.append('>')
        into.extend(self.format_children(self.children))
        self._start_cache = into
        return into

    def end(self):
        return [f'</{self.tag}>'] if not self.void else ['']


class base_element_void(base_element):
    void = True


class Component:
    def __init__(self, into, i, j):
        self.into = into
        self.i = i
        self.j = j

    def delete(self):
        for i in range(self.i, self.j):
            c.hypergen.into[i] = DELETED


def component(func):
    @wraps(func)
    def _(*args, **kwargs):
        with c(into=contextlist('target_id'), at='hypergen'):
            func(*args, **kwargs)
            into = c.hypergen.into
        i = len(c.hypergen.into)
        c.hypergen.into.extend(into)
        j = len(c.hypergen.into)
        return Component(into, i, j)

    return _


class input_(base_element_void):
    def __init__(self, *children, **attrs):
        type_ = attrs.get('type_', attrs.pop('type', None))
        if type_:
            attrs['type_'] = type_
        if type_ == 'radio':
            assert attrs.get('name'), 'Name must be set for radio buttons.'
        super().__init__(*children, **attrs)

    def attribute(self, key, value):
        if key != 'value':
            return super().attribute(key, value)
        type_ = self.attrs.get('type_', None)
        if type_ == 'datetime-local' and type(value) is datetime:
            return [' ', key, '="', value.strftime('%Y-%m-%dT%H:%M:%S'), '"']
        if type_ == 'month' and type(value) is dict:
            return [' ', key, '="', f'{value["year"]:04}-{value["month"]:02}', '"']
        if type_ == 'week' and type(value) is dict:
            return [' ', key, '="', f'{value["year"]:04}-W{value["week"]:02}', '"']
        return super().attribute(key, value)


class a(base_element):
    def __init__(self, *children, **attrs):
        class_active = attrs.pop('class_active', None)
        href = attrs.get('href')
        if class_active and href:
            from flask_hypergen.liveview import url_is_active

            if url_is_active(href):
                attrs['class'] = add_class(attrs.get('class'), class_active)
        super().__init__(*children, **attrs)


class link(base_element):
    def __init__(self, href=OMIT, rel='stylesheet', **attrs):
        type_ = attrs.get('type_', attrs.pop('type', 'text/css'))
        attrs['type_'] = type_
        attrs['href'] = href
        super().__init__(rel=rel, **attrs)


class script(base_element):
    def __init__(self, *children, **attrs):
        attrs['t'] = lambda x, **kwargs: x
        super().__init__(*children, **attrs)


class style(base_element):
    def __init__(self, *children, **attrs):
        attrs['t'] = lambda x, **kwargs: x
        super().__init__(*children, **attrs)


def doctype(type_='html'):
    raw('<!DOCTYPE ', type_, '>')


_TAG_NAMES = [
    'abbr',
    'acronym',
    'address',
    'applet',
    'area',
    'article',
    'aside',
    'audio',
    'b',
    'base',
    'basefont',
    'bdi',
    'bdo',
    'big',
    'blockquote',
    'body',
    'br',
    'button',
    'canvas',
    'caption',
    'center',
    'cite',
    'code',
    'col',
    'colgroup',
    'data',
    'datalist',
    'dd',
    'del_',
    'details',
    'dfn',
    'dialog',
    'dir_',
    'div',
    'dl',
    'dt',
    'em',
    'embed',
    'fieldset',
    'figcaption',
    'figure',
    'font',
    'footer',
    'form',
    'frame',
    'frameset',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'head',
    'header',
    'hr',
    'html',
    'i',
    'iframe',
    'img',
    'ins',
    'kbd',
    'label',
    'legend',
    'li',
    'main',
    'map_',
    'mark',
    'meta',
    'meter',
    'nav',
    'noframes',
    'noscript',
    'object_',
    'ol',
    'optgroup',
    'option',
    'output',
    'p',
    'param',
    'picture',
    'pre',
    'progress',
    'q',
    'rp',
    'rt',
    'ruby',
    's',
    'samp',
    'section',
    'select',
    'small',
    'source',
    'span',
    'strike',
    'strong',
    'sub',
    'summary',
    'sup',
    'svg',
    'table',
    'tbody',
    'td',
    'template',
    'textarea',
    'tfoot',
    'th',
    'thead',
    'time_',
    'title',
    'tr',
    'track',
    'tt',
    'u',
    'ul',
    'var',
    'video',
    'wbr',
]
_VOID_TAGS = {
    'area',
    'base',
    'br',
    'col',
    'embed',
    'hr',
    'img',
    'meta',
    'param',
    'source',
    'track',
    'wbr',
}
for _name in _TAG_NAMES:
    if _name in globals():
        continue
    base_cls = base_element_void if _name in _VOID_TAGS else base_element
    globals()[_name] = type(_name, (base_cls,), {})
time = time_

__all__ = [
    *_TAG_NAMES,
    'COMMANDS',
    'Component',
    'FULL',
    'HTML',
    'HYPERGEN_RETURNS',
    'OMIT',
    'TemplatePlugin',
    'a',
    'add_class',
    'base_element',
    'base_element_void',
    'component',
    'doctype',
    'hprint',
    'hypergen',
    'hypergen_to_response',
    'input_',
    'join_html',
    'link',
    'on_url',
    'raw',
    'script',
    'style',
    'time',
    'write',
]
