class CuemsWsServerError(Exception):
    pass
class FileIntegrityError(CuemsWsServerError):
    pass
class NonExistentItemError(CuemsWsServerError):
    pass