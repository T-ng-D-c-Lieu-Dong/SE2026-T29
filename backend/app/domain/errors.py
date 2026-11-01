class BookingError(Exception):
    """Base class for expected booking errors."""


class InvalidSlot(BookingError):
    """The requested start time is not a valid booking slot."""


class SlotAlreadyBooked(BookingError):
    """Another active booking already owns the requested slot."""


class AppointmentNotFound(BookingError):
    """The requested appointment does not exist."""


class ExportUnauthenticated(BookingError):
    """The export request has no valid API key."""


class ExportForbidden(BookingError):
    """The caller is authenticated but not allowed to export this scope."""


class InvalidExportRange(BookingError):
    """The requested export date window is invalid."""
