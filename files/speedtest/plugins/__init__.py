import os
import pkgutil
import importlib

plugins = []

def load_plugins():
    """Load plugins if get_results is defined."""
    global plugins
    # iterate over all python modules in "plugins" and load configured plugins
    for _, name, _ in pkgutil.iter_modules([os.path.dirname(__file__)]):
        module = importlib.import_module(__name__ + '.' + name)
        for symbol_name in dir(module):
            if symbol_name == 'get_results':
                plugins.append(module)
