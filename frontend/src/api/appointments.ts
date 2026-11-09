import type {
  Appointment,
  AppointmentList,
  CreateAppointmentInput,
  Slot,
  VersionInfo,
} from "../types";
import { apiFetch } from "./client";

export function fetchSlots(date: string): Promise<Slot[]> {
  return apiFetch<Slot[]>(`/api/slots?date=${encodeURIComponent(date)}`);
}

export function listAppointments(limit: number, offset: number): Promise<AppointmentList> {
  return apiFetch<AppointmentList>(`/api/appointments?limit=${limit}&offset=${offset}`);
}

export function createAppointment(input: CreateAppointmentInput): Promise<Appointment> {
  return apiFetch<Appointment>("/api/appointments", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function cancelAppointment(id: string): Promise<void> {
  return apiFetch<void>(`/api/appointments/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function fetchVersion(): Promise<VersionInfo> {
  return apiFetch<VersionInfo>("/api/version");
}
