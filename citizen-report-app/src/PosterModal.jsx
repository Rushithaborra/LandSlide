import { QRCodeSVG } from "qrcode.react";
import { X, Printer } from "lucide-react";

/**
 * A printable QR poster pointing back at this same reporting form, meant for
 * physical posting on village noticeboards and bus stops so residents who
 * see it can scan straight into the form on their own phone. Encodes
 * wherever this app actually is running (its own origin), so it needs no
 * hardcoded URL and no backend change to stay correct across deploys.
 */
export default function PosterModal({ onClose }) {
  const reportUrl = `${window.location.origin}${window.location.pathname}`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 print:bg-white print:p-0"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="poster-print relative w-full max-w-sm rounded-lg bg-white p-6 text-center print:max-w-none print:rounded-none print:p-0 print:shadow-none"
        style={{ border: "1px solid #DAD4C6" }}
      >
        <button
          onClick={onClose}
          className="absolute right-4 top-4 rounded-full p-1 print:hidden"
          style={{ background: "#EFEBE1" }}
          aria-label="Close"
        >
          <X size={16} color="#5B6359" />
        </button>

        <p
          className="text-lg font-bold"
          style={{ fontFamily: "'Zilla Slab', serif", color: "#22332B" }}
        >
          Seen a landslide warning sign?
        </p>
        <p className="mt-1 text-sm" style={{ color: "#5B6359" }}>
          Scan to report ground conditions — cracks, slope movement, or blocked roads.
        </p>

        <div className="mt-5 flex justify-center">
          <div className="rounded-md p-3" style={{ background: "#FFFFFF", border: "1px solid #DAD4C6" }}>
            <QRCodeSVG value={reportUrl} size={200} level="M" />
          </div>
        </div>

        <p className="mt-4 break-all text-xs" style={{ color: "#8A8578" }}>
          {reportUrl}
        </p>
        <p className="mt-3 text-xs" style={{ color: "#8A8578" }}>
          Landslide Early Warning System — for post on village noticeboards and bus stops
        </p>

        <button
          onClick={() => window.print()}
          className="mt-5 flex w-full items-center justify-center gap-2 rounded-md py-2.5 text-sm font-semibold print:hidden"
          style={{ background: "#22332B", color: "#F0EDE4" }}
        >
          <Printer size={16} /> Print poster
        </button>
      </div>
    </div>
  );
}
