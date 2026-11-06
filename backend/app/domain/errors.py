class BookingError(Exception):
    """Base class for expected booking errors."""


class InvalidSlot(BookingError):
    """The requested start time is not a valid booking slot."""


class SlotAlreadyBooked(BookingError):
    """Another active booking already owns the requested slot."""


class AppointmentNotFound(BookingError):
    """The requested appointment does not exist."""


class DraftNotFound(BookingError):
    """The requested draft does not exist."""


class StaleDraftRevision(BookingError):
    """A save arrived with a revision that is not newer than the stored draft."""

    def __init__(self, current: object) -> None:
        super().__init__("A newer revision of this draft is already saved")
        self.current = current
