class EMSError(Exception):
    """Base class for all domain errors."""


class DuplicateEmailError(EMSError):
    pass


class NotFoundError(EMSError):
    def __init__(self, entity: str, identifier):
        self.entity = entity
        self.identifier = identifier
        super().__init__(f"{entity} {identifier} not found")


class CourseFullError(EMSError):
    def __init__(self, course_id: int, capacity: int):
        self.course_id = course_id
        self.capacity = capacity
        super().__init__(f"Course {course_id} has no seats left (capacity {capacity})")


class AlreadyEnrolledError(EMSError):
    pass


class InvalidSemesterError(EMSError):
    pass


class PaymentRequiredError(EMSError):
    pass


class DuplicateAttendanceError(EMSError):
    pass
