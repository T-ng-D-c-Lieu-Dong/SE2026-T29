import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { BookingPage } from "./pages/BookingPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5_000,
    },
  },
});

export function App(): ReactNode {
  return (
    <QueryClientProvider client={queryClient}>
      <BookingPage />
    </QueryClientProvider>
  );
}
