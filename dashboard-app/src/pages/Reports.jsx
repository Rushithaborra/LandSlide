import DashboardLayout from "../layouts/DashboardLayout";
import { FileText } from "lucide-react";

/**
 * LINK SPOT — not in the original pipeline diagram; this is a suggested
 * addition. Wire this up to a backend endpoint that generates a PDF/CSV
 * export of a chosen date range once that feature is built.
 */
export default function Reports() {
  return (
    <DashboardLayout title="Reports" subtitle="Generate and download risk & rainfall reports">
      <div className="bg-white rounded-xl border border-paper-200 p-10 flex flex-col items-center justify-center text-center gap-3">
        <FileText size={28} className="text-paper-400" />
        <p className="text-sm text-paper-600 max-w-sm">
          Report generation isn't wired up yet. TODO: connect to the export
          endpoint once the backend team adds it (see LINKING_GUIDE.md).
        </p>
      </div>
    </DashboardLayout>
  );
}
