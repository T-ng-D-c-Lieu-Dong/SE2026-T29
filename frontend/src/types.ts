export type AppointmentStatus = "booked" | "cancelled";

export interface Appointment {
  id: string;
  customer_name: string;
  starts_at: string;
  status: AppointmentStatus;
  created_at: string;
  cancelled_at: string | null;
}

export interface AppointmentList {
  items: Appointment[];
  total: number;
  limit: number;
  offset: number;
}

export interface Slot {
  starts_at: string;
}

export interface VersionInfo {
  release: string;
  commit_sha: string;
  environment?: string;
  fault_active?: boolean;
}

export interface CreateAppointmentInput {
  customer_name: string;
  starts_at: string;
}
