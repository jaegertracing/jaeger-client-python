from .normalizer import NameNormalizer


class Operation(object):
    def __init__(self, max_size=200):
        from threading import Lock
        self.lock = Lock()
        self.names = dict()
        self.max_size = max_size
        self.normalizer = NameNormalizer()

    def normalize(self, name):
        with self.lock:
            if name in self.names:
                return self.names[name]
            if len(self.names) >= self.max_size:
                return ''
            return self.normalize_with_lock(name)

    def normalize_with_lock(self, name):
        norm = self.normalizer.normalize(name)
        self.names[name] = norm
        return norm
