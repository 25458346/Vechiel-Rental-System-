"""Run pip-audit with an in-memory HTTP cache for restricted Windows folders."""
import runpy

from cachecontrol.cache import DictCache
import pip_audit._cli
import pip_audit._cache


class MemoryCache(DictCache):
    def __init__(self, directory):
        super().__init__()


pip_audit._cache._SafeFileCache = MemoryCache
runpy.run_module("pip_audit", run_name="__main__")
