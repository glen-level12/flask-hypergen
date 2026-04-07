from __future__ import annotations

from contextlib import contextmanager

from flask_hypergen import (
    body,
    button,
    div,
    doctype,
    h1,
    head,
    header,
    html,
    input_,
    link,
    main,
    meta,
    p,
    style,
    title,
)


def page_head(title_text: str) -> None:
    meta(charset='utf-8')
    meta(name='viewport', content='width=device-width, initial-scale=1')
    title(title_text)
    link('https://cdn.simplecss.org/simple.min.css')
    style('#content { min-height: 4rem; } .stack { display:flex; gap:0.5rem; flex-wrap:wrap; }')


def make_base_template(title_text: str):
    @contextmanager
    def base_template():
        doctype()
        with html(lang='en'):
            with head():
                page_head(title_text)
            with body():
                header(h1(title_text), p('Flask adapter example for django-hypergen.'))
                with main(id_='content'):
                    yield

    base_template.target_id = 'content'
    return base_template


def counter_fragment(n: int, increment_callback):
    p('Counter value:')
    input_(id_='n', value=n, readonly=True)
    div(button('Increment', id_='increment', onclick=increment_callback), class_='stack')
