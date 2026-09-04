import { BrowserRouter, Routes, Route } from "react-router-dom";
import Overview from "./pages/Overview";
import LiveMap from "./pages/LiveMap";
import Alerts from "./pages/Alerts";
import Reports from "./pages/Reports";
import Incidents from "./pages/Incidents";
import DataObservations from "./pages/DataObservations";
import CitizenReports from "./pages/CitizenReports";
import Settings from "./pages/Settings";
import HelpDocs from "./pages/HelpDocs";

/**
 * All page routes live here. Match this list against the sidebar links in
 * src/components/Sidebar.jsx if you ever add/remove a page.
 */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/live-map" element={<LiveMap />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/incidents" element={<Incidents />} />
        <Route path="/data-observations" element={<DataObservations />} />
        <Route path="/citizen-reports" element={<CitizenReports />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/help" element={<HelpDocs />} />
      </Routes>
    </BrowserRouter>
  );
}
