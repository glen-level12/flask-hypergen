from flask import Flask

from flask_hypergen import init_app
import flask_hypergen.examples.apptemplate as apptemplate
import flask_hypergen.examples.commands as commands
import flask_hypergen.examples.hellocoreonly as hellocoreonly
import flask_hypergen.examples.hellohypergen as hellohypergen
import flask_hypergen.examples.inputs as inputs
from flask_hypergen.examples.sqlalchemy_counter import default_database_url
from flask_hypergen.examples.sqlalchemy_counter import make_blueprint as make_sqlalchemy_blueprint


def create_app(testing=False, database_url=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY='flask-hypergen-dev', TESTING=testing)
    init_app(app)
    app.register_blueprint(hellocoreonly.bp)
    app.register_blueprint(hellohypergen.bp)
    app.register_blueprint(inputs.bp)
    app.register_blueprint(commands.bp)
    app.register_blueprint(apptemplate.bp)
    app.register_blueprint(make_sqlalchemy_blueprint(database_url or default_database_url()))
    return app
