export const BOOKING_TIME_ZONE = "Asia/Ho_Chi_Minh";

const datePartsFormatter = new Intl.DateTimeFormat("en-US", {
  timeZone: BOOKING_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const timeFormatter = new Intl.DateTimeFormat("vi-VN", {
  timeZone: BOOKING_TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const dateFormatter = new Intl.DateTimeFormat("vi-VN", {
  timeZone: BOOKING_TIME_ZONE,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

function readPart(parts: Intl.DateTimeFormatPart[], type: Intl.DateTimeFormatPartTypes): string {
  return parts.find((part) => part.type === type)?.value ?? "";
}

/** Calendar date (YYYY-MM-DD) of an instant in the booking timezone. */
export function dateInBookingZone(value: Date): string {
  const parts = datePartsFormatter.formatToParts(value);
  const year = readPart(parts, "year");
  const month = readPart(parts, "month");
  const day = readPart(parts, "day");
  if (!year || !month || !day) {
    throw new Error("Không thể xác định ngày theo múi giờ Asia/Ho_Chi_Minh");
  }
  return `${year}-${month}-${day}`;
}

/** Today's calendar date in the booking timezone, not the machine's timezone. */
export function todayInBookingZone(now: Date = new Date()): string {
  return dateInBookingZone(now);
}

/** "HH:mm" of an ISO timestamp in the booking timezone. */
export function formatTime(value: string | Date): string {
  return timeFormatter.format(new Date(value));
}

/** "DD/MM/YYYY" of an ISO timestamp in the booking timezone. */
export function formatDate(value: string | Date): string {
  return dateFormatter.format(new Date(value));
}

/** "DD/MM/YYYY HH:mm" of an ISO timestamp in the booking timezone. */
export function formatDateTime(value: string | Date): string {
  return `${formatDate(value)} ${formatTime(value)}`;
}

/** Adds whole days to a YYYY-MM-DD calendar date without timezone drift. */
export function addDays(date: string, days: number): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!match) {
    throw new Error(`Ngày không hợp lệ: ${date}`);
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const shifted = new Date(Date.UTC(year, month - 1, day + days));
  return shifted.toISOString().slice(0, 10);
}
