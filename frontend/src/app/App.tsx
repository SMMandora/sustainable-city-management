import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NavLink, Route, BrowserRouter as Router, Routes } from "react-router-dom";
import { BikeMapPage } from "../features/bikes/BikeMapPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, refetchOnWindowFocus: false },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <header>
          <h1>Sustainable City Management</h1>
          <nav>
            <NavLink to="/" end>
              Bikes
            </NavLink>
          </nav>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<BikeMapPage />} />
          </Routes>
        </main>
      </Router>
    </QueryClientProvider>
  );
}
