import { describe, expect, it } from "vitest";
import {
  addDays,
  dateInBookingZone,
  formatDate,
  formatDateTime,
  formatTime,
  todayInBookingZone,
} from "./time";

describe("time helpers", () => {
  it("formats an offset timestamp in Asia/Ho_Chi_Minh", () => {
    const value = "2026-10-27T08:00:00+07:00";

    expect(formatTime(value)).toBe("08:00");
    expect(formatDate(value)).toBe("27/10/2026");
    expect(formatDateTime(value)).toBe("27/10/2026 08:00");
  });

  it("converts a UTC instant to the Vietnamese calendar date", () => {
    const lateUtc = new Date("2026-10-25T18:30:00Z");

    expect(dateInBookingZone(lateUtc)).toBe("2026-10-26");
    expect(todayInBookingZone(lateUtc)).toBe("2026-10-26");
  });

  it("adds days across month boundaries without timezone drift", () => {
    expect(addDays("2026-10-31", 2)).toBe("2026-11-02");
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
  });

  it("rejects malformed calendar dates", () => {
    expect(() => addDays("31-10-2026", 1)).toThrow(/Ngày không hợp lệ/);
  });
});
