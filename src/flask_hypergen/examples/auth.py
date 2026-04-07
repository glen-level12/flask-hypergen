from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from flask import Blueprint, abort, redirect, request, url_for
from flask_login import UserMixin, current_user, login_user, logout_user

from flask_hypergen import LOGIN_REQUIRED, action, callback, liveview
from flask_hypergen.examples.common import make_base_template
from flask_hypergen.tags import a, button, h2, p


bp = Blueprint('auth', __name__, url_prefix='/auth')
BASE_TEMPLATE = make_base_template('Authentication')


@dataclass
class DemoUser(UserMixin):
    id: str
    permissions: frozenset[str] = field(default_factory=frozenset)

    def has_perm(self, permission: str) -> bool:
        return permission in self.permissions

    def has_perms(self, permissions: Iterable[str]) -> bool:
        return set(permissions) <= set(self.permissions)


_DEMO_USERS = {
    'viewer': DemoUser('viewer'),
    'editor': DemoUser('editor', frozenset({'examples.edit'})),
}


def user_load(user_id: str):
    return _DEMO_USERS.get(user_id)


def protected_template(message: str, *, show_action: bool = False) -> None:
    h2('Authenticated view')
    p(message, id_='auth-message')
    p(f'Signed in as {current_user.id}', id_='auth-status')
    p(a('Log out', href=url_for('auth.logout')))
    if show_action:
        button(
            'Run authorized action',
            id_='auth-update',
            onclick=callback(update_message, 'Updated from an authorized action.'),
        )


@bp.get('/login')
def login():
    user = user_load(request.args.get('user', 'editor'))
    if user is None:
        abort(404)
    login_user(user, remember=False)
    return redirect(request.args.get('next') or url_for('auth.protected'))


@bp.get('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@liveview(
    bp,
    '/protected',
    perm=LOGIN_REQUIRED,
    base_template=BASE_TEMPLATE,
    login_url='auth.login',
)
def protected(request) -> None:
    protected_template('This page requires an authenticated user.')


@liveview(bp, '/editor', perm='examples.edit', base_template=BASE_TEMPLATE, login_url='auth.login')
def editor(request) -> None:
    protected_template('This page requires the examples.edit permission.', show_action=True)


@action(
    bp,
    '/update',
    perm='examples.edit',
    target_id='content',
    base_view=editor,
    login_url='auth.login',
)
def update_message(request, message: str) -> None:
    protected_template(message, show_action=True)
