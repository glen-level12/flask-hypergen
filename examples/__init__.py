from flask import Flask


def create_app(testing: bool = False, database_url: str | None = None) -> Flask:
    from examples.app import create_app as _create_app

    return _create_app(testing=testing, database_url=database_url)


__all__ = ['create_app']
