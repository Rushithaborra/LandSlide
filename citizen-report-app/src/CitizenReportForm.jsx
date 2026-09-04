import { useState, useRef, useEffect } from "react";
import {
  MapPin,
  Camera,
  Send,
  WifiOff,
  Wifi,
  CheckCircle2,
  TriangleAlert,
  X,
  Navigation,
  Image as ImageIcon,
  Mic,
  MicOff,
} from "lucide-react";

// ---------------------------------------------------------------------------
// BACKEND — set VITE_API_BASE_URL in a .env file at the project root.
// Local dev (no .env, or backend running on your machine): falls back to
// http://localhost:8000. Production: set VITE_API_BASE_URL to the real
// Render URL once deployed — no code change needed here again.
// ---------------------------------------------------------------------------
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function generateClientReportId() {
  if (crypto?.randomUUID) return crypto.randomUUID();
  // Fallback for browsers without crypto.randomUUID (older Safari/webviews)
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { method: "GET" });
    if (!res.ok) return false;
    const data = await res.json();
    return data.status === "ok";
  } catch {
    return false;
  }
}

// Parses FastAPI's structured 422 validation errors into one readable line.
// Falls back to the raw string when `detail` isn't the pydantic list shape.
function parseBackendError(detail) {
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg).join(" · ");
  }
  if (typeof detail === "string") return detail;
  return "Something went wrong sending the report — try again.";
}

async function submitReport(payload, photoFile) {
  const formData = new FormData();
  formData.append("data", JSON.stringify(payload));
  if (photoFile) formData.append("photo", photoFile);

  const res = await fetch(`${API_BASE}/reports`, {
    method: "POST",
    body: formData,
    // No Content-Type header set on purpose — the browser sets the correct
    // multipart boundary automatically. Setting it manually breaks the upload.
  });

  const body = await res.json();
  if (!res.ok) {
    throw new Error(parseBackendError(body.detail));
  }
  return body; // full report object, see backend_api_for_E.pdf
}

const REPORT_TYPES = [
  { id: "crack", label: "Ground crack" },
  { id: "movement", label: "Slope movement" },
  { id: "road", label: "Blocked road" },
  { id: "other", label: "Other hazard" },
];

const SEVERITIES = [
  { id: "low", label: "Low", tone: "#5B7A5E" },
  { id: "moderate", label: "Moderate", tone: "#B08328" },
  { id: "high", label: "High", tone: "#B0521E" },
  { id: "critical", label: "Critical", tone: "#9A2F1F" },
];

export default function CitizenReportForm() {
  const [online, setOnline] = useState(
    typeof navigator !== "undefined" ? navigator.onLine : true
  );
  const [reportType, setReportType] = useState(null);
  const [severity, setSeverity] = useState(null);
  const [locating, setLocating] = useState(false);
  const [coords, setCoords] = useState(null);
  const [locationError, setLocationError] = useState("");
  const [placeName, setPlaceName] = useState("");
  const [photo, setPhoto] = useState(null);
  const [photoPreview, setPhotoPreview] = useState(null);
  const [description, setDescription] = useState("");
  const [reporterName, setReporterName] = useState("");
  const [reporterPhone, setReporterPhone] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(null);
  const [formError, setFormError] = useState("");
  const [recent, setRecent] = useState([]);
  const [listening, setListening] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(true);
  const [voiceError, setVoiceError] = useState("");
  const fileInputRef = useRef(null);
  const recognitionRef = useRef(null);
  const baseDescriptionRef = useRef("");
  const clientReportIdRef = useRef(null);
  const [backendReachable, setBackendReachable] = useState(null); // null = checking

  useEffect(() => {
    const goOnline = () => setOnline(true);
    const goOffline = () => setOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  // Checks the tunnel is actually alive, since it's a temporary Cloudflare
  // URL that dies whenever Sushanth's machine or tunnel restarts — separate
  // from the browser's own online/offline state.
  useEffect(() => {
    let cancelled = false;
    checkBackendHealth().then((ok) => {
      if (!cancelled) setBackendReachable(ok);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // ---------------------------------------------------------------------
  // Voice-based description (Web Speech API).
  // Support is inconsistent across browsers (solid on Chrome/Android,
  // weak/absent on Safari/iOS) and it needs a live connection in most
  // implementations, so it's a convenience for good-signal areas, not
  // part of the offline story. Falls back silently to typing if
  // unsupported.
  // ---------------------------------------------------------------------
  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceSupported(false);
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-IN";

    recognition.onresult = (event) => {
      let interim = "";
      let final = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) final += transcript;
        else interim += transcript;
      }
      if (final) baseDescriptionRef.current += final;
      setDescription((baseDescriptionRef.current + " " + interim).trim());
    };

    recognition.onerror = (event) => {
      setListening(false);
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setVoiceError("Microphone permission was blocked — allow it in browser settings to use voice.");
      } else if (event.error === "no-speech") {
        setVoiceError("Didn't catch that — tap and try speaking again.");
      } else if (event.error === "network") {
        setVoiceError("Voice input needs a live connection — try typing instead.");
      } else {
        setVoiceError("Voice input couldn't start on this browser — typing works fine.");
      }
    };
    recognition.onend = () => setListening(false);

    recognitionRef.current = recognition;
    return () => recognition.stop();
  }, []);

  function toggleListening() {
    if (!voiceSupported || !recognitionRef.current) return;
    setVoiceError("");
    if (listening) {
      recognitionRef.current.stop();
      setListening(false);
    } else {
      baseDescriptionRef.current = description ? description + " " : "";
      recognitionRef.current.start();
      setListening(true);
    }
  }

  function captureLocation() {
    setLocationError("");
    if (!navigator.geolocation) {
      setLocationError("Location isn't available on this device.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        });
        setLocating(false);
      },
      (err) => {
        setLocationError(
          "Couldn't get GPS location. Enter the nearest village or landmark instead."
        );
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  function handlePhotoChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setPhoto(file);
    const reader = new FileReader();
    reader.onload = () => setPhotoPreview(reader.result);
    reader.readAsDataURL(file);
  }

  function removePhoto() {
    setPhoto(null);
    setPhotoPreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function resetForm() {
    if (listening && recognitionRef.current) {
      recognitionRef.current.stop();
      setListening(false);
    }
    baseDescriptionRef.current = "";
    clientReportIdRef.current = null;
    setReportType(null);
    setSeverity(null);
    setCoords(null);
    setPlaceName("");
    setPhoto(null);
    setPhotoPreview(null);
    setDescription("");
    setReporterName("");
    setReporterPhone("");
    setSubmitted(null);
    setFormError("");
  }

  async function handleSubmit() {
    if (listening && recognitionRef.current) {
      recognitionRef.current.stop();
      setListening(false);
    }
    setFormError("");
    if (!reportType) return setFormError("Choose what you're reporting.");
    if (!severity) return setFormError("Pick how urgent it looks.");
    if (!coords && !placeName.trim())
      return setFormError("Add a location — GPS or a place name.");
    if (!description.trim() || description.trim().length < 5)
      return setFormError("Describe what you're seeing (at least 5 characters).");

    setSubmitting(true);

    // Generated once per report attempt and kept stable across retries, so
    // resubmitting the same report after a dropped connection doesn't create
    // a duplicate on the backend — see backend_api_for_E.pdf, "Data contract".
    if (!clientReportIdRef.current) {
      clientReportIdRef.current = generateClientReportId();
    }

    const payload = {
      client_report_id: clientReportIdRef.current,
      reportType,
      severity,
      coords,
      placeName: placeName.trim(),
      description: description.trim(),
      reporterName: reporterName.trim(),
      reporterPhone: reporterPhone.trim(),
      capturedAt: new Date().toISOString(),
    };

    try {
      const result = await submitReport(payload, photo);
      setSubmitting(false);
      setSubmitted(result.id);
      clientReportIdRef.current = null; // done — next report gets a fresh id
      setRecent((prev) => [
        {
          id: result.id,
          type: REPORT_TYPES.find((t) => t.id === reportType)?.label,
          place: result.place_name || (coords ? "GPS location" : "—"),
          severity: result.severity,
          time: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
          thumb: photoPreview,
        },
        ...prev,
      ]);
    } catch (err) {
      setSubmitting(false);
      // client_report_id is kept as-is here on purpose — tapping "Send" again
      // retries the same report instead of creating a duplicate.
      setFormError(err.message || "Couldn't send the report — check your connection and try again.");
    }
  }

  return (
    <div
      className="min-h-screen w-full flex justify-center px-4 py-8"
      style={{ background: "#EFEBE1", fontFamily: "'Public Sans', sans-serif" }}
    >
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Zilla+Slab:wght@500;700&family=Public+Sans:wght@400;500;600;700&display=swap');
      `}</style>

      <div className="w-full max-w-md">
        {/* Header */}
        <div className="flex items-start justify-between mb-5">
          <div>
            <h1
              className="text-2xl leading-tight"
              style={{
                fontFamily: "'Zilla Slab', serif",
                fontWeight: 700,
                color: "#22332B",
              }}
            >
              Report ground conditions
            </h1>
            <p className="text-sm mt-1" style={{ color: "#5B6359" }}>
              Cracks, slope movement, or blocked roads — takes under a minute.
            </p>
          </div>
        </div>

        {/* Connectivity banner */}
        <div
          className="flex items-center gap-2 rounded-md px-3 py-2 mb-2 text-sm"
          style={{
            background: online ? "#E4E9DE" : "#F2E2D6",
            color: online ? "#3F5A3F" : "#8A4A1E",
          }}
        >
          {online ? <Wifi size={16} /> : <WifiOff size={16} />}
          <span>
            {online
              ? "Connected — reports send immediately."
              : "No connection — offline queueing isn't wired up yet in this build."}
          </span>
        </div>
        {backendReachable === false && (
          <div
            className="flex items-center gap-2 rounded-md px-3 py-2 mb-5 text-sm"
            style={{ background: "#F2D6D2", color: "#9A2F1F" }}
          >
            <TriangleAlert size={16} />
            <span>
              Backend isn't responding — the tunnel URL may have changed. Ask
              Sushanth for the current one.
            </span>
          </div>
        )}
        {backendReachable !== false && <div className="mb-3" />}

        {submitted ? (
          <div
            className="rounded-lg p-6 text-center"
            style={{ background: "#FFFFFF", border: "1px solid #DAD4C6" }}
          >
            <CheckCircle2
              size={40}
              style={{ color: "#3F6B3F", margin: "0 auto" }}
            />
            <h2
              className="text-lg mt-3"
              style={{ fontFamily: "'Zilla Slab', serif", fontWeight: 700, color: "#22332B" }}
            >
              Report sent
            </h2>
            <p className="text-sm mt-1" style={{ color: "#5B6359" }}>
              Reference {submitted}. It'll appear on the district dashboard shortly.
            </p>
            <button
              onClick={resetForm}
              className="mt-4 px-4 py-2 rounded-md text-sm font-semibold"
              style={{ background: "#22332B", color: "#F0EDE4" }}
            >
              Submit another report
            </button>
          </div>
        ) : (
          <div
            className="rounded-lg p-5 flex flex-col gap-5"
            style={{ background: "#FFFFFF", border: "1px solid #DAD4C6" }}
          >
            {/* Report type */}
            <div>
              <label
                className="text-xs font-semibold uppercase tracking-wide"
                style={{ color: "#8A8578" }}
              >
                What are you seeing?
              </label>
              <div className="grid grid-cols-2 gap-2 mt-2">
                {REPORT_TYPES.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setReportType(t.id)}
                    className="text-sm rounded-md px-3 py-2 text-left border"
                    style={{
                      borderColor: reportType === t.id ? "#22332B" : "#DAD4C6",
                      background: reportType === t.id ? "#22332B" : "#FBFAF6",
                      color: reportType === t.id ? "#F0EDE4" : "#2E332D",
                      fontWeight: reportType === t.id ? 600 : 400,
                    }}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Severity */}
            <div>
              <label
                className="text-xs font-semibold uppercase tracking-wide"
                style={{ color: "#8A8578" }}
              >
                How urgent does it look?
              </label>
              <div className="flex gap-2 mt-2">
                {SEVERITIES.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setSeverity(s.id)}
                    className="flex-1 text-xs rounded-md py-2 border font-semibold"
                    style={{
                      borderColor: severity === s.id ? s.tone : "#DAD4C6",
                      background: severity === s.id ? s.tone : "#FBFAF6",
                      color: severity === s.id ? "#FFFFFF" : "#2E332D",
                    }}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Location */}
            <div>
              <label
                className="text-xs font-semibold uppercase tracking-wide"
                style={{ color: "#8A8578" }}
              >
                Location
              </label>
              <button
                onClick={captureLocation}
                disabled={locating}
                className="mt-2 w-full flex items-center justify-center gap-2 rounded-md py-2 text-sm font-semibold border"
                style={{
                  borderColor: coords ? "#3F6B3F" : "#DAD4C6",
                  background: coords ? "#E4E9DE" : "#FBFAF6",
                  color: coords ? "#3F5A3F" : "#2E332D",
                }}
              >
                {coords ? <Navigation size={16} /> : <MapPin size={16} />}
                {locating
                  ? "Getting your location…"
                  : coords
                  ? `Captured (±${Math.round(coords.accuracy)}m)`
                  : "Capture GPS location"}
              </button>
              {coords && (
                <p className="text-xs mt-1" style={{ color: "#8A8578" }}>
                  {coords.lat.toFixed(5)}, {coords.lng.toFixed(5)}
                </p>
              )}
              {locationError && (
                <p className="text-xs mt-1 flex items-center gap-1" style={{ color: "#9A2F1F" }}>
                  <TriangleAlert size={12} /> {locationError}
                </p>
              )}
              <input
                type="text"
                placeholder="Nearest village, road, or landmark"
                value={placeName}
                onChange={(e) => setPlaceName(e.target.value)}
                className="mt-2 w-full rounded-md px-3 py-2 text-sm border outline-none"
                style={{ borderColor: "#DAD4C6", color: "#2E332D" }}
              />
            </div>

            {/* Photo */}
            <div>
              <label
                className="text-xs font-semibold uppercase tracking-wide"
                style={{ color: "#8A8578" }}
              >
                Photo (optional but helpful)
              </label>
              {photoPreview ? (
                <div className="relative mt-2">
                  <img
                    src={photoPreview}
                    alt="Captured hazard"
                    className="w-full h-40 object-cover rounded-md"
                  />
                  <button
                    onClick={removePhoto}
                    className="absolute top-2 right-2 rounded-full p-1"
                    style={{ background: "#22332B" }}
                  >
                    <X size={14} color="#F0EDE4" />
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="mt-2 w-full flex items-center justify-center gap-2 rounded-md py-6 text-sm font-semibold border border-dashed"
                  style={{ borderColor: "#C7C0AE", color: "#5B6359" }}
                >
                  <Camera size={18} /> Add photo
                </button>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handlePhotoChange}
                className="hidden"
              />
            </div>

            {/* Description */}
            <div>
              <div className="flex items-center justify-between">
                <label
                  className="text-xs font-semibold uppercase tracking-wide"
                  style={{ color: "#8A8578" }}
                >
                  What's happening
                </label>
                {voiceSupported && (
                  <button
                    onClick={toggleListening}
                    className="flex items-center gap-1 text-xs font-semibold rounded-full px-2 py-1"
                    style={{
                      background: listening ? "#9A2F1F" : "#EFEBE1",
                      color: listening ? "#FFFFFF" : "#5B6359",
                    }}
                  >
                    {listening ? <MicOff size={12} /> : <Mic size={12} />}
                    {listening ? "Listening…" : "Speak instead"}
                  </button>
                )}
              </div>
              <textarea
                value={description}
                onChange={(e) => {
                  baseDescriptionRef.current = e.target.value;
                  setDescription(e.target.value);
                }}
                rows={3}
                placeholder="e.g. Fresh crack across the road, widening after last night's rain"
                className="mt-2 w-full rounded-md px-3 py-2 text-sm border outline-none resize-none"
                style={{
                  borderColor: listening ? "#9A2F1F" : "#DAD4C6",
                  color: "#2E332D",
                }}
              />
              {!voiceSupported && (
                <p className="text-xs mt-1" style={{ color: "#8A8578" }}>
                  Voice input isn't supported on this browser — typing works fine.
                </p>
              )}
              {voiceError && (
                <p className="text-xs mt-1 flex items-center gap-1" style={{ color: "#9A2F1F" }}>
                  <TriangleAlert size={12} /> {voiceError}
                </p>
              )}
            </div>

            {/* Reporter details */}
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Your name (optional)"
                value={reporterName}
                onChange={(e) => setReporterName(e.target.value)}
                className="rounded-md px-3 py-2 text-sm border outline-none"
                style={{ borderColor: "#DAD4C6", color: "#2E332D" }}
              />
              <input
                type="tel"
                placeholder="Phone (optional)"
                value={reporterPhone}
                onChange={(e) => setReporterPhone(e.target.value)}
                className="rounded-md px-3 py-2 text-sm border outline-none"
                style={{ borderColor: "#DAD4C6", color: "#2E332D" }}
              />
            </div>

            {formError && (
              <p className="text-sm flex items-center gap-1" style={{ color: "#9A2F1F" }}>
                <TriangleAlert size={14} /> {formError}
              </p>
            )}

            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="w-full flex items-center justify-center gap-2 rounded-md py-3 text-sm font-semibold"
              style={{ background: "#B0521E", color: "#FFFFFF" }}
            >
              <Send size={16} />
              {submitting ? "Sending…" : "Send report"}
            </button>
          </div>
        )}

        {/* Recent reports (session-only demo feed) */}
        {recent.length > 0 && (
          <div className="mt-6">
            <h3
              className="text-xs font-semibold uppercase tracking-wide mb-2"
              style={{ color: "#8A8578" }}
            >
              Sent this session
            </h3>
            <div className="flex flex-col gap-2">
              {recent.map((r) => (
                <div
                  key={r.id}
                  className="flex items-center gap-3 rounded-md p-2"
                  style={{ background: "#FFFFFF", border: "1px solid #DAD4C6" }}
                >
                  <div
                    className="w-10 h-10 rounded-md flex items-center justify-center shrink-0 overflow-hidden"
                    style={{ background: "#EFEBE1" }}
                  >
                    {r.thumb ? (
                      <img src={r.thumb} className="w-full h-full object-cover" />
                    ) : (
                      <ImageIcon size={16} color="#8A8578" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold truncate" style={{ color: "#2E332D" }}>
                      {r.type} · {r.place}
                    </p>
                    <p className="text-xs" style={{ color: "#8A8578" }}>
                      {r.id} · {r.time}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
