from contextlib import contextmanager
import pickle

from flask import session

from flask_hypergen.context import context


class AppstatePlugin:
    def __init__(self, namespace, appstate):
        self.namespace = namespace
        self.appstate = appstate

    @contextmanager
    def context(self):
        key = f'hypergen_appstate_{self.namespace}'
        appstate = session.get(key, None)
        if appstate is not None:
            appstate = pickle.loads(appstate.encode('latin1'))
        else:
            appstate = self.appstate()
        with context(at='hypergen', appstate=appstate):
            yield
            session[key] = pickle.dumps(
                context.hypergen.appstate,
                pickle.HIGHEST_PROTOCOL,
            ).decode('latin1')
