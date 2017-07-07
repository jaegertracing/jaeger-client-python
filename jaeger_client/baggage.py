DEFAULT_MAX_VALUE_LENGTH = 2048

class BaggageRestrictionManager(object):
    """
    BaggageRestrictionManager is responsible for deciding if a baggage key
    is valid.
    """

    # def __init__(self, tags=None):
    #     self._tags = tags

    def is_valid_baggage_key(self, baggage_key):
        raise NotImplementedError()


class DefaultBaggageRestrictionManager(BaggageRestrictionManager):
    """
    DefaultBaggageRestrictionManager adjAFHSALFHASFLKSAHDLSAFSADAS
    """
    def is_valid_baggage_key(self, baggage_key):
        return True, DEFAULT_MAX_VALUE_LENGTH


class RemoteBaggageRestrictionManager(BaggageRestrictionManager):
    """
    RemoteBaggageRestrictionManager adjAFHSALFHASFLKSAHDLSAFSADAS
    """
    def is_valid_baggage_key(self, baggage_key):
        return True, DEFAULT_MAX_VALUE_LENGTH

