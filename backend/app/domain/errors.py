class BookingError(Exception):
    """Base class for expected booking errors."""


class InvalidSlot(BookingError):
    """The requested start time is not a valid booking slot."""


class SlotAlreadyBooked(BookingError):
    """Another active booking already owns the requested slot."""


class AppointmentNotFound(BookingError):
    """The requested appointment does not exist."""


class AccessDeniedError(BookingError):
    """The caller does not have permission to access or modify this appointment."""
