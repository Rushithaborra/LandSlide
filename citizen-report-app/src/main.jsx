import React from "react";
import ReactDOM from "react-dom/client";
import { registerSW } from "virtual:pwa-register";
import CitizenReportForm from "./CitizenReportForm.jsx";
import "./index.css";

// See vite.config.js's injectRegister: false comment -- this is the real
// auto-update mechanism (checks for a new service worker on load, then
// reloads automatically the moment it activates) that the plugin's default
// injected register script doesn't actually provide on its own.
registerSW({ immediate: true });

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <CitizenReportForm />
  </React.StrictMode>
);
