from __future__ import annotations

from typing import Protocol

from flask import Blueprint

from flask_hypergen import NO_PERM_REQUIRED, a, div, h2, liveview, p
from flask_hypergen.examples.common import make_base_template


bp = Blueprint('partialload', __name__, url_prefix='/partialload')
BASE_TEMPLATE = make_base_template('Partial Load')


class ReversibleView(Protocol):
    __name__: str

    def reverse(self) -> str: ...


def page_template(
    page_name: str,
    first_link: ReversibleView,
    second_link: ReversibleView,
) -> None:
    h2('Partial loading with history support')
    p('This example demonstrates shared base-template navigation with browser history support.')
    p(f'Current page: {page_name}', id_='partial-page')
    div(
        a(first_link.__name__, href=first_link.reverse(), id_=first_link.__name__),
        a(second_link.__name__, href=second_link.reverse(), id_=second_link.__name__),
        class_='stack',
    )


@liveview(bp, '/page1', perm=NO_PERM_REQUIRED, base_template=BASE_TEMPLATE)
def page1(request) -> None:
    page_template('page1', page2, page3)


@liveview(bp, '/page2', perm=NO_PERM_REQUIRED, base_template=BASE_TEMPLATE)
def page2(request) -> None:
    page_template('page2', page1, page3)


@liveview(bp, '/page3', perm=NO_PERM_REQUIRED, base_template=BASE_TEMPLATE)
def page3(request) -> None:
    page_template('page3', page1, page2)
