from contextlib import contextmanager
from datetime import date, datetime
import re

from pyrsistent import pmap
import pytest
from werkzeug.exceptions import Forbidden

from examples.common import make_base_template
import flask_hypergen
from flask_hypergen import (
    FULL,
    LOGIN_REQUIRED,
    THIS,
    call_js,
    check_perms,
    command,
    component,
    doctype,
    dumps,
    hypergen,
    loads,
)
from flask_hypergen.context import context, context_middleware, contextlist
from flask_hypergen.hypergen import compare_funcs
from flask_hypergen.liveview import LiveviewPlugin
from flask_hypergen.liveview import callback as cb
from flask_hypergen.tags import (
    a,
    body,
    div,
    h1,
    h2,
    head,
    html,
    input_,
    li,
    p,
    span,
    td,
    textarea,
    title,
    tr,
    ul,
)
from flask_hypergen.template import TemplatePlugin, join_html

from .conftest import (
    HttpResponse,
    Request,
    User,
    hypergen_context,
    mock_hypergen_callback,
    mock_middleware,
)


def normalized_html():
    return re.sub(r'[0-9]{5,}', '1234', join_html(context.hypergen.into))


def test_context():
    context.replace(request=Request(), user=User())
    assert context.request.user.id == 1
    assert 'request' in context
    context['feature_flag'] = True
    assert context.feature_flag is True


def test_context_cm():
    def inc(ctx):
        return ctx.set('i', ctx.get('i', 0) + 1)

    with context(inc):
        assert context['i'] == 1
        with context(inc, foo=9):
            assert context['foo'] == 9
            assert context['i'] == 2
            with context(bar=42):
                assert context['i'] == 2
                assert context['bar'] == 42
            assert context['i'] == 2
        assert context['i'] == 1
        assert 'foo' not in context


def test_context_immutable():
    with context(my_appname=pmap({'title': 'foo', 'items': [1, 2, 3]})):
        with context(at='my_appname', items=[4, 5]):
            assert context.my_appname['title'] == 'foo'
            assert context['my_appname']['items'] == [4, 5]
        assert context['my_appname']['items'] == [1, 2, 3]


def test_context_mutable_update_should_fail():
    with (
        context(my_appname={'title': 'foo', 'items': [1, 2, 3]}),
        pytest.raises(TypeError, match='Not immutable context variable attempted updated'),
        context(at='my_appname', items=[4, 5]),
    ):
        pass


def test_context_at_creation():
    with context(at='my_appname', title='foo', items=[1, 2, 3]):
        with context(at='my_appname', items=[4, 5]):
            assert context['my_appname']['title'] == 'foo'
            assert context['my_appname']['items'] == [4, 5]
        assert context['my_appname']['items'] == [1, 2, 3]


def test_context_middleware():
    def view(request):
        assert context.user.pk == 1
        assert context['request'].user.pk == 1
        return HttpResponse()

    context_middleware(lambda request: view(request))(Request())


def test_check_perms_any_perm_matches_subset():
    request = Request()
    request.user.permissions = frozenset({'examples.view'})

    result = check_perms(request, ('examples.edit', 'examples.view'), any_perm=True)

    assert result.ok is True
    assert result.matched_perms == {'examples.view'}


def test_check_perms_raise_exception_for_login_required():
    request = Request()
    request.user.is_authenticated = False

    with pytest.raises(Forbidden):
        check_perms(request, LOGIN_REQUIRED, raise_exception=True)


@pytest.mark.xfail(
    reason='Django legacy middleware compatibility is intentionally not part of flask_hypergen',
)
def test_context_middleware_old():
    raise AssertionError()


def test_element():
    with context(at='hypergen', **hypergen_context()):
        div('hello world!')
        assert join_html(context.hypergen.into) == '<div>hello world!</div>'
    with context(at='hypergen', **hypergen_context()):
        with div('a', class_='foo'):
            div('b', x_foo=42)
        assert normalized_html() == '<div class="foo">a<div x-foo="42">b</div></div>'
    with context(at='hypergen', **hypergen_context()):

        @div('a', class_='foo')
        def f1():
            div('b', x_foo=42)

        f1()
        assert normalized_html() == '<div class="foo">a<div x-foo="42">b</div></div>'
    with context(at='hypergen', **hypergen_context()):
        div('a', None, div('b', x_foo=42), class_='foo')
        assert normalized_html() == '<div class="foo">a<div x-foo="42">b</div></div>'
    with context(at='hypergen', **hypergen_context()):
        div(None, [1, 2], sep='-')
        assert normalized_html() == '<div>1-2</div>'
    with context(at='hypergen', **hypergen_context()):
        ul([li([li(y) for y in range(3, 4)]) for _x in range(1, 2)])
        assert normalized_html() == '<ul><li><li>3</li></li></ul>'
    with context(at='hypergen', **hypergen_context()):
        ul(li(li(y) for y in range(3, 4)) for _x in range(1, 2))
        assert normalized_html() == '<ul><li><li>3</li></li></ul>'
    with context(at='hypergen', **hypergen_context()):
        div([1, 2], div(1, 2, div(1, None, 2, ul([li(x) for x in range(1, 3)]))))
        assert (
            normalized_html()
            == '<div>12<div>12<div>12<ul><li>1</li><li>2</li></ul></div></div></div>'
        )
    with context(at='hypergen', **hypergen_context()):
        ul(
            None,
            [
                li(None, (li(li(z) for z in range(1, 2)) for _y in range(3, 4)), None)
                for _x in range(5, 6)
            ],
            None,
        )
        assert normalized_html() == '<ul><li><li><li>1</li></li></li></ul>'


def test_live_element():
    with context(is_test=True):

        @mock_hypergen_callback
        def my_callback():
            pass

        with context(is_test=True, at='hypergen', **hypergen_context()):
            div('hello world!', onclick=cb('my_url', 42), id_='i1')
            assert (
                normalized_html() == '<div onclick="hypergen.event(event, \'i1__onclick\')" '
                'id="i1">hello world!</div>'
            )
        with context(is_test=True, at='hypergen', **hypergen_context()):
            source = input_(name='a', id_='field-a')
            input_(name='b', id_='field-b', onclick=cb(my_callback, source))
            assert normalized_html() == (
                '<input name="a" id="field-a"/><input name="b" id="field-b" '
                'onclick="hypergen.event(event, \'field-b__onclick\')"/>'
            )
        with context(is_test=True, at='hypergen', **hypergen_context()):
            message = textarea(placeholder='myplace', id_='message-input')
            with div(class_='message'):
                with div(class_='action-left'):
                    span('Annullér', class_='clickable')
                with div(class_='action-right'):
                    span(
                        'Send',
                        class_='clickable',
                        onclick=cb(my_callback, message),
                        id_='send-message',
                    )
                div(message, class_='form form-write')
            assert normalized_html() == (
                '<div class="message"><div class="action-left">'
                '<span class="clickable">Annullér</span></div>'
                '<div class="action-right"><span class="clickable" '
                'onclick="hypergen.event(event, \'send-message__onclick\')" '
                'id="send-message">Send</span></div>'
                '<div class="form form-write"><textarea placeholder="myplace" '
                'id="message-input"></textarea></div></div>'
            )
        with context(is_test=True, at='hypergen', **hypergen_context()):
            input_(autofocus=True)
            assert join_html(context.hypergen.into) == '<input autofocus/>'


def test_live_element2():
    with context(is_test=True):

        @mock_hypergen_callback
        def my_callback():
            pass

        with context(is_test=True, at='hypergen', **hypergen_context()):
            el1 = input_(
                id_='id_new_password',
                placeholder='Adgangskode',
                oninput=cb(my_callback, THIS, ''),
            )
            el2 = input_(
                id_='el2',
                placeholder='Gentag Adgangskode',
                oninput=cb(my_callback, THIS, el1),
            )
            h2('Skift Adgangskode')
            p('Rules:')
            with div(class_='form'), div():
                with ul(id_='password_verification_smartassness'):
                    div('TODO')
                with div(class_='form'):
                    div(el1, class_='form-field')
                    div(el2, class_='form-field')
                    div('Skift adgangskode', class_='button disabled')
            assert normalized_html() == (
                '<h2>Skift Adgangskode</h2><p>Rules:</p><div class="form"><div>'
                '<ul id="password_verification_smartassness"><div>TODO</div></ul>'
                '<div class="form"><div class="form-field"><input id="id_new_password" '
                'placeholder="Adgangskode" '
                'oninput="hypergen.event(event, \'id_new_password__oninput\')"/></div>'
                '<div class="form-field"><input id="el2" '
                'placeholder="Gentag Adgangskode" '
                'oninput="hypergen.event(event, \'el2__oninput\')"/></div>'
                '<div class="button disabled">'
                'Skift adgangskode</div></div></div></div>'
            )


def test_callback():
    with context(is_test=True, at='hypergen', **hypergen_context()):

        @mock_hypergen_callback
        def f1(foo, punk=300):
            pass

        element = input_(oninput=cb(f1, THIS, 200, debounce=500), id_='testcb')
        assert isinstance(cb('foo', 42, debounce=42)(element, 'oninput', 92), list)


def test_components():
    def f1():
        div('a')

    @component
    def f2():
        div('a')

    with context(is_test=True, at='hypergen', **hypergen_context()):
        div(1, f1(), 2)
        assert normalized_html() == '<div>a</div><div>12</div>'
    with context(is_test=True, at='hypergen', **hypergen_context()):
        div(1, f2(), 2)
        assert normalized_html() == '<div>1<div>a</div>2</div>'


def test_components2():
    @component
    def comp1():
        @component
        def comp2():
            input_(value='a')

        comp2()

    with context(is_test=True, at='hypergen', **hypergen_context()):
        with tr():
            td(comp1())
        assert normalized_html() == '<tr><td><input value="a"/></td></tr>'
    with context(is_test=True, at='hypergen', **hypergen_context()):
        with tr(), td():
            comp1()
        assert normalized_html() == '<tr><td><input value="a"/></td></tr>'


def test_js_value_func():
    @mock_middleware()
    def inner():
        def template():
            body()
            i = input_()
            assert (i.js_value_func, i.js_coerce_func) == ('hypergen.read.value', None)
            i = input_(js_value_func='a', js_coerce_func='b')
            assert (i.js_value_func, i.js_coerce_func) == ('a', 'b')
            i = input_(js_value_func='a', coerce_to=float)
            assert (i.js_value_func, i.js_coerce_func) == ('a', 'hypergen.coerce.float')
            i = input_(js_value_func='a', coerce_to=int)
            assert (i.js_value_func, i.js_coerce_func) == ('a', 'hypergen.coerce.int')
            i = input_(js_value_func='a', coerce_to=str)
            assert (i.js_value_func, i.js_coerce_func) == ('a', 'hypergen.coerce.str')
            i = input_(js_value_func='a', type='date')
            assert (i.js_value_func, i.js_coerce_func) == ('a', 'hypergen.coerce.date')
            i = input_(js_value_func='a', type_='datetime-local')
            assert (i.js_value_func, i.js_coerce_func) == ('a', 'hypergen.coerce.datetime')
            i = input_(js_value_func='a', type_='weidewokvocxkokwoekvd')
            assert (i.js_value_func, i.js_coerce_func) == ('a', None)

        hypergen(template, settings={'action': True, 'target_id': 'foo'})
        hypergen(template, settings={'liveview': True, 'target_id': 'foo'})

    inner()


def test_eventhandler_cache():
    @mock_middleware()
    def inner():
        def template():
            body()
            input_(onclick=cb('/path/to/cb/', THIS), id_='tec')
            handlers = dict(enumerate(context.hypergen.event_handler_callbacks.values()))
            assert dumps(handlers) == (
                '{"0":["hypergen.callback","/path/to/cb/",[["_","element_value",'
                '["hypergen.read.value",null,"tec"]]],{"debounce":0,"confirm_":false,'
                '"blocks":false,"uploadFiles":false,"clear":false,"elementId":"tec",'
                '"debug":false,"meta":{},"headers":{},"eachUrlBlocks":true,"timeout":20000}]}'
            )

        hypergen(template, settings={'liveview': True, 'target_id': 'foo'})
        hypergen(template, settings={'action': True, 'target_id': 'foo'})

    inner()


def test_call_js():
    @mock_middleware()
    def inner():
        def template():
            body()
            a(onclick=call_js('hypergen.xyz', THIS), id_='tcj')
            assert dumps(list(context.hypergen.event_handler_callbacks.values())) == (
                '[["hypergen.xyz",["_","element_value",["hypergen.read.value",null,"tcj"]]]]'
            )

        hypergen(template, settings={'liveview': True, 'target_id': 'foo'})
        hypergen(template, settings={'action': True, 'target_id': 'foo'})

    inner()


def test_command_prepend():
    with context(at='hypergen', **hypergen_context()):
        command('hypergen.appended')
        command('hypergen.prepended', prepend=True)

        assert list(context.hypergen.commands) == [
            ['hypergen.prepended'],
            ['hypergen.appended'],
        ]


def test_repr():
    with context(is_test=True, at='hypergen', **hypergen_context()):
        el1 = input_(id_='el1')
        el2 = input_(onclick=cb('alert', el1), id_='el2')
        assert (
            repr(el2) == 'input_(onclick=callback("alert", input_(id_="el1"), '
            'eachUrlBlocks=True, timeout=20000), id_="el2")'
        )


def test_serialization():
    payload = {
        'string': 'hi',
        'int': 42,
        'float': 9.9,
        'list': [1, 2, 3],
        'range': range(1, 10, 2),
        'dict': {'key': 'value'},
        'set': {1, 2, 3},
        'frozenset': frozenset({1, 2, 3}),
        'date': date(2022, 1, 1),
        'datetime': datetime(2022, 1, 1, 10, 11, 23),
    }
    assert loads(dumps(payload)) == payload


def test_loads_integer_keys():
    assert loads('{"1":{"_":["tuple",[1,2]]},"two":2}', integer_keys=True) == {
        1: (1, 2),
        'two': 2,
    }


@mock_middleware()
def test_plugins():
    def template(n):
        with html():
            with head():
                title(2)
            with body():
                h1('4')

    def template2(n):
        html(head(title(2)), body(h1('4')))

    html1 = hypergen(
        template,
        2,
        settings={'plugins': [TemplatePlugin(), LiveviewPlugin()], 'indent': True},
    )
    html2 = hypergen(
        template2,
        2,
        settings={'plugins': [TemplatePlugin(), LiveviewPlugin()], 'indent': True},
    )
    expected_html = '\n'.join(
        [
            '<html>',
            '    <head>',
            '        <!--hypergen_liveview_media-->',
            '        <script src="/flask_hypergen/static/hypergen.js"></script>',
            '        <script type="application/json" id="hypergen-apply-commands-data">'
            '{"_":["deque",[["hypergen.setClientState","hypergen.eventHandlerCallbacks",{}],'
            '["history.replaceState",{"callback_url":"mock"},"","mock"]]]}</script>',
            '        <script>',
            '                hypergen.ready(() => hypergen.applyCommands('
            'JSON.parse(document.getElementById(',
            "                    'hypergen-apply-commands-data').textContent, hypergen.reviver)))",
            '            </script>',
            '        <title>',
            '            2',
            '        </title>',
            '    </head>',
            '    <body>',
            '        <h1>',
            '            4',
            '        </h1>',
            '    </body>',
            '</html>',
        ],
    )
    assert html1.strip() == html2.strip() == expected_html


def test_flask_hypergen_public_api():
    exported = set(dir(flask_hypergen))
    assert {
        'ContextMiddleware',
        'LOGIN_REQUIRED',
        'NO_PERM_REQUIRED',
        'TemplatePlugin',
        'action',
        'callback',
        'command',
        'context',
        'context_init_app',
        'context_middleware',
        'contextlist',
        'hypergen',
        'init_app',
        'liveview',
        'route_register',
    } <= exported


def test_multilist():
    with context(at='hypergen'):
        into = contextlist('target_id')
        into.append(1)
        assert into == [1]
    with context(at='hypergen', target_id='bar'):
        into.append(2)
        into.append(3)
    assert into.contexts == {'__default_context__': [1], 'bar': [2, 3]}


@mock_middleware()
def test_multitargets():
    def template():
        p('main')
        with context(at='hypergen', target_id='foo'):
            p('foo1')
        with context(at='hypergen', target_id='bar'):
            p('bar1')

    full = hypergen(template, settings={'returns': FULL})
    assert full['html'] == '<p>main</p>'
    assert {k: join_html(v) for k, v in full['context'].hypergen.into.contexts.items()} == {
        '__default_context__': '<p>main</p>',
        'foo': '<p>foo1</p>',
        'bar': '<p>bar1</p>',
    }


@mock_middleware()
def test_inject_html():
    def template1():
        doctype()
        with html():
            a('b')

    def template2():
        a('b')

    x = hypergen(template1, settings={'liveview': True, 'indent': True}).strip()
    y = hypergen(template2, settings={'liveview': True, 'indent': True}).strip()
    assert '<script src="/flask_hypergen/static/hypergen.js"></script>' in x
    assert '<head>' in x and '<a>' in x
    assert y.startswith('<!--hypergen_liveview_media-->')


def foo():
    def bar():
        pass

    return bar


def foz():
    def bar():
        pass

    return bar


def alt_template_factory():
    @contextmanager
    def alt_template():
        yield

    return alt_template


def test_function_equality():
    a, b, c = foo(), foo(), foz()
    assert not compare_funcs(make_base_template('one'), alt_template_factory())
    assert compare_funcs(a, b)
    assert not compare_funcs(a, foo)
    assert not compare_funcs(a, c)
