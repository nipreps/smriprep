import atexit
from contextlib import ExitStack
from pathlib import Path

try:
    from functools import cache
except ImportError:  # PY38
    from functools import lru_cache as cache

try:  # Prefer backport to leave consistency to dependency spec
    from importlib_resources import files, as_file
except ImportError:
    from importlib.resources import files, as_file

__all__ = ["load_resource"]

exit_stack = ExitStack()
atexit.register(exit_stack.close)

path = files(__package__)


@cache
def load_resource(fname: str) -> Path:
    return exit_stack.enter_context(as_file(path.joinpath(fname)))
