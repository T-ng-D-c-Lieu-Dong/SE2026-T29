import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cancelAppointment,
  createAppointment,
  fetchSlots,
  fetchVersion,
  listAppointments,
} from "../api/appointments";
import { ConflictError, describeError, type ErrorDescription } from "../api/client";
import { AppointmentList } from "../components/AppointmentList";
import { ErrorBanner, StatusBanner } from "../components/Banners";
import { BookingForm } from "../components/BookingForm";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { SlotList } from "../components/SlotList";
import { EnvironmentBadge, VersionFooter } from "../components/VersionFooter";
import { todayInBookingZone } from "../time";
import type { Appointment, CreateAppointmentInput } from "../types";

const PAGE_SIZE = 20;

export function BookingPage(): ReactNode {
  const queryClient = useQueryClient();
  const [selectedDate, setSelectedDate] = useState<string>(() => todayInBookingZone());
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);
  const [customerName, setCustomerName] = useState("");
  const [page, setPage] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<ErrorDescription | null>(null);
  const [cancelTarget, setCancelTarget] = useState<Appointment | null>(null);

  const slotsQuery = useQuery({
    queryKey: ["slots", selectedDate],
    queryFn: () => fetchSlots(selectedDate),
  });

  const appointmentsQuery = useQuery({
    queryKey: ["appointments", page],
    queryFn: () => listAppointments(PAGE_SIZE, page * PAGE_SIZE),
  });

  const versionQuery = useQuery({
    queryKey: ["version"],
    queryFn: fetchVersion,
    retry: 1,
    staleTime: 30_000,
  });

  async function refreshBookings(): Promise<void> {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["slots"] }),
      queryClient.invalidateQueries({ queryKey: ["appointments"] }),
    ]);
  }

  const bookingMutation = useMutation({
    mutationFn: (input: CreateAppointmentInput) => createAppointment(input),
    onSuccess: () => {
      setError(null);
      setNotice("Đặt lịch thành công.");
      setCustomerName("");
      setSelectedSlot(null);
      void refreshBookings();
    },
    onError: (mutationError: unknown) => {
      setNotice(null);
      setError(describeError(mutationError));
      if (mutationError instanceof ConflictError) {
        setSelectedSlot(null);
        void queryClient.invalidateQueries({ queryKey: ["slots"] });
      }
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (appointmentId: string) => cancelAppointment(appointmentId),
    onSuccess: () => {
      setError(null);
      setNotice("Đã huỷ lịch.");
      setCancelTarget(null);
      void refreshBookings();
    },
    onError: (mutationError: unknown) => {
      setNotice(null);
      setError(describeError(mutationError));
      setCancelTarget(null);
    },
  });

  const slotsError = slotsQuery.error ? describeError(slotsQuery.error) : null;
  const appointmentsError = appointmentsQuery.error ? describeError(appointmentsQuery.error) : null;
  const environment = versionQuery.data?.environment;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Booking API</p>
          <h1>Đặt lịch hẹn</h1>
          <p className="subtitle">Chọn ngày, chọn slot trống và giữ chỗ trong vài giây.</p>
        </div>
        <EnvironmentBadge environment={environment} />
      </header>

      <main className="layout">
        <section className="panel" aria-labelledby="slots-heading">
          <div className="panel__header">
            <h2 id="slots-heading">Slot trống</h2>
            <label className="field field--inline">
              <span>Ngày</span>
              <input
                type="date"
                name="booking_date"
                value={selectedDate}
                onChange={(event) => {
                  setSelectedDate(event.target.value);
                  setSelectedSlot(null);
                  setNotice(null);
                  setError(null);
                  setPage(0);
                }}
              />
            </label>
          </div>

          <div className="feedback">
            {notice ? <StatusBanner message={notice} /> : null}
            {error ? <ErrorBanner message={error.message} traceId={error.traceId} /> : null}
          </div>

          <SlotList
            slots={slotsQuery.data}
            isLoading={slotsQuery.isPending}
            error={slotsError}
            selectedSlot={selectedSlot}
            disabled={bookingMutation.isPending}
            onSelect={(startsAt) => {
              setSelectedSlot(startsAt);
              setNotice(null);
              setError(null);
            }}
            onRetry={() => {
              void slotsQuery.refetch();
            }}
          />

          <BookingForm
            selectedSlot={selectedSlot}
            customerName={customerName}
            isPending={bookingMutation.isPending}
            onNameChange={setCustomerName}
            onSubmit={() => {
              if (!selectedSlot) {
                return;
              }
              setNotice(null);
              setError(null);
              bookingMutation.mutate({
                customer_name: customerName.trim(),
                starts_at: selectedSlot,
              });
            }}
          />
        </section>

        <section className="panel" aria-labelledby="appointments-heading">
          <div className="panel__header">
            <h2 id="appointments-heading">Lịch đã đặt</h2>
          </div>
          <AppointmentList
            data={appointmentsQuery.data}
            isLoading={appointmentsQuery.isPending}
            error={appointmentsError}
            page={page}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
            onRequestCancel={(appointment) => {
              setNotice(null);
              setError(null);
              setCancelTarget(appointment);
            }}
            onRetry={() => {
              void appointmentsQuery.refetch();
            }}
          />
        </section>
      </main>

      <VersionFooter
        version={versionQuery.data}
        isLoading={versionQuery.isPending}
        isError={versionQuery.isError}
      />

      <ConfirmDialog
        appointment={cancelTarget}
        isPending={cancelMutation.isPending}
        onConfirm={() => {
          if (cancelTarget) {
            cancelMutation.mutate(cancelTarget.id);
          }
        }}
        onCancel={() => {
          setCancelTarget(null);
        }}
      />
    </div>
  );
}
