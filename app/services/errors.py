class ServiceError(Exception):
    pass


class NotFoundError(ServiceError):
    pass


class PermissionDeniedError(ServiceError):
    pass


class InvalidStateError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass


class NoAssignmentError(ServiceError):
    pass
