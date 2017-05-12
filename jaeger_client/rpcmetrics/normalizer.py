SAFE_CHARACTER_SET = [
    ['a', 'z'],
    ['A', 'Z'],
    ['0', '9'],
    ['-', '-'],
    ['_', '_'],
    ['/', '/'],
    ['.', '.'],
]

class NameNormalizer(object):
    """
    NameNormalizer is used to convert the endpoint names to strings
    that can be safely used as tags in the metrics.
    """
    def __init__(self):
        pass

    def normalize(self, name):
        l = list(name)
        for i, c in enumerate(l):
            if not self.safe_character(c):
                l[i] = '-'
        return ''.join(l)

    def safe_character(self, c):
        for set in SAFE_CHARACTER_SET:
            if set[0] <= c <= set[1]:
                return True
        return False
