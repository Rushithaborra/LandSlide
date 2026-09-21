import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AlertTriangle, CloudRain, LocateFixed, MapPin, Phone, Search, ShieldCheck, TriangleAlert, Volume2, VolumeX } from "lucide-react";
import DashboardLayout from "../layouts/DashboardLayout";
import SurroundingsPanel from "../components/SurroundingsPanel";
import { fetchLiveRainfall, geocodePlace, getAreaRisk, getRainfallStatus } from "../services/api";

// Colour AND icon AND word: the level must be readable without reading much.
const TIER_STYLE = {
  high: { box: "border-risk-high bg-risk-highSoft dark:bg-risk-high/15", text: "text-risk-high dark:text-risk-highOn", icon: TriangleAlert },
  moderate: { box: "border-risk-moderate bg-risk-moderateSoft dark:bg-risk-moderate/15", text: "text-risk-moderate dark:text-risk-moderateOn", icon: AlertTriangle },
  low: { box: "border-risk-low bg-risk-lowSoft dark:bg-risk-low/15", text: "text-risk-low dark:text-risk-lowOn", icon: ShieldCheck },
  unscored: { box: "border-paper-300 bg-paper-100 dark:bg-night-800", text: "text-paper-600 dark:text-paper-400", icon: MapPin },
};

// India Meteorological Department's daily-rainfall classes (mm in 24 h).
function rainClass(mm) {
  if (mm < 2.5) return "none";
  if (mm < 15.6) return "light";
  if (mm < 64.5) return "moderate";
  if (mm < 115.6) return "heavy";
  if (mm < 204.5) return "veryHeavy";
  return "extreme";
}

const sum = (rows) => rows.reduce((total, r) => total + r.intensity_mm, 0);

// Rain summary for the spot: today, the last 3 observed days, the next 2 forecast days.
function summariseRain(readings) {
  const observed = readings.filter((r) => !r.is_forecast).sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  const forecast = readings.filter((r) => r.is_forecast);
  const today = observed[observed.length - 1];
  return {
    todayMm: today ? today.intensity_mm : null,
    last3Mm: sum(observed.slice(-3)),
    forecastMm: sum(forecast.slice(0, 2)),
  };
}

const SPEECH_LANG = { en: "en-IN", hi: "hi-IN", ne: "ne-NP" };

// Read-aloud for people who read slowly or not at all. Uses the device's own
// voices; the button is hidden when the device has none for the chosen language
// (Nepali voices in particular are often missing) rather than reading Nepali
// text in the wrong voice.
function useSpeech(language) {
  const [hasVoice, setHasVoice] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const prefix = (SPEECH_LANG[language] || "en-IN").split("-")[0];

  useEffect(() => {
    if (!supported) return undefined;
    const check = () => setHasVoice(window.speechSynthesis.getVoices().some((v) => v.lang.toLowerCase().startsWith(prefix)));
    check();
    window.speechSynthesis.addEventListener("voiceschanged", check);
    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", check);
      window.speechSynthesis.cancel();
    };
  }, [supported, prefix]);

  const speak = useCallback(
    (text) => {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = SPEECH_LANG[language] || "en-IN";
      utterance.onend = () => setSpeaking(false);
      utterance.onerror = () => setSpeaking(false);
      setSpeaking(true);
      window.speechSynthesis.speak(utterance);
    },
    [language],
  );
  const stop = useCallback(() => {
    window.speechSynthesis.cancel();
    setSpeaking(false);
  }, []);

  return { canSpeak: supported && hasVoice, speaking, speak, stop };
}

export default function CheckArea() {
  const { t, i18n } = useTranslation();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState(params.get("q") || "");
  const [phase, setPhase] = useState("idle"); // idle | searching | choosing | assessing | done | error
  const [message, setMessage] = useState(null); // translated error/info text
  const [places, setPlaces] = useState([]);
  const [result, setResult] = useState(null);
  const speech = useSpeech(i18n.language);
  const runId = useRef(0); // ignore answers from a search the user has since replaced

  const assess = useCallback(async (place) => {
    const id = ++runId.current;
    setPhase("assessing");
    setMessage(null);
    const [risk, rain, status] = await Promise.allSettled([
      getAreaRisk(place.lat, place.lng),
      fetchLiveRainfall(place.lat, place.lng, { pastDays: 3, forecastDays: 3 }),
      getRainfallStatus(),
    ]);
    if (id !== runId.current) return;
    if (risk.status === "rejected") {
      setPhase("error");
      setMessage(t("checkArea.loadError"));
      return;
    }
    const state = risk.value.zone?.state;
    const alertingStates = status.status === "fulfilled" ? status.value?.alerting_states : null;
    setResult({
      place,
      risk: risk.value,
      rain: rain.status === "fulfilled" ? summariseRain(rain.value) : null,
      // null = unknown; never claim "no alert" for a state that isn't being watched.
      alertingHere: state && Array.isArray(alertingStates) ? alertingStates.some((s) => s.toLowerCase() === state.toLowerCase()) : null,
    });
    setPhase("done");
  }, [t]);

  const search = useCallback(
    async (text) => {
      const q = text.trim();
      if (q.length < 2) return;
      const id = ++runId.current;
      setParams({ q }, { replace: true });
      setPhase("searching");
      setMessage(null);
      setResult(null);
      try {
        const found = await geocodePlace(q, i18n.language);
        if (id !== runId.current) return;
        if (found.length === 0) {
          setPhase("error");
          setMessage(t("checkArea.noPlaces"));
        } else if (found.length === 1) {
          assess(found[0]);
        } else {
          setPlaces(found);
          setPhase("choosing");
        }
      } catch {
        if (id !== runId.current) return;
        setPhase("error");
        setMessage(t("checkArea.searchError"));
      }
    },
    [assess, i18n.language, setParams, t],
  );

  // Arriving from the Overview search box (?q=...) runs the search straight away; arriving
  // from a landslide record (?lat=&lng=&name=) assesses that exact place.
  useEffect(() => {
    const lat = Number(params.get("lat"));
    const lng = Number(params.get("lng"));
    if (params.get("lat") && params.get("lng") && Number.isFinite(lat) && Number.isFinite(lng)) {
      assess({ name: params.get("name") || t("checkArea.yourLocation"), detail: "", lat, lng });
    } else if (params.get("q")) search(params.get("q"));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, on arrival
  }, []);

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setPhase("error");
      setMessage(t("checkArea.locationDenied"));
      return;
    }
    setPhase("searching");
    setMessage(null);
    setResult(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => assess({ name: t("checkArea.yourLocation"), detail: "", lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => {
        setPhase("error");
        setMessage(t("checkArea.locationDenied"));
      },
      { timeout: 15000, maximumAge: 60000 },
    );
  };

  const busy = phase === "searching" || phase === "assessing";

  return (
    <DashboardLayout title={t("checkArea.title")} subtitle={t("checkArea.subtitle")}>
      <div className="mx-auto w-full max-w-2xl space-y-5">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            search(query);
          }}
          className="rounded-xl border border-paper-200 bg-white p-5 dark:border-night-700 dark:bg-night-900"
        >
          <label htmlFor="area-query" className="mb-2 block text-sm font-medium text-ink-900 dark:text-paper-100">
            {t("checkArea.label")}
          </label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <Search size={18} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-paper-500" />
              <input
                id="area-query"
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("checkArea.placeholder")}
                className="w-full rounded-lg border border-paper-200 bg-paper-50 py-3 pl-10 pr-3 text-base text-paper-700 placeholder:text-paper-500 focus:outline-none focus:ring-2 focus:ring-teal-600/30 dark:border-night-700 dark:bg-night-800 dark:text-paper-300"
              />
            </div>
            <button
              type="submit"
              disabled={busy || query.trim().length < 2}
              className="rounded-lg bg-teal-600 px-5 py-3 text-base font-medium text-white hover:bg-teal-700 disabled:opacity-50"
            >
              {t("checkArea.search")}
            </button>
          </div>
          <button
            type="button"
            onClick={useMyLocation}
            disabled={busy}
            className="mt-3 inline-flex items-center gap-2 rounded-lg border border-paper-200 px-4 py-2.5 text-sm font-medium text-paper-700 hover:bg-paper-100 disabled:opacity-50 dark:border-night-700 dark:text-paper-300 dark:hover:bg-night-800"
          >
            <LocateFixed size={16} />
            {t("checkArea.useMyLocation")}
          </button>
        </form>

        {busy && <p className="text-center text-sm text-paper-500">{t("common.loading")}</p>}

        {message && (
          <div role="alert" className="rounded-xl border border-paper-200 bg-white p-4 text-sm text-paper-700 dark:border-night-700 dark:bg-night-900 dark:text-paper-300">
            {message}
          </div>
        )}

        {phase === "choosing" && (
          <div className="rounded-xl border border-paper-200 bg-white p-4 dark:border-night-700 dark:bg-night-900">
            <p className="mb-2 text-sm font-medium text-ink-900 dark:text-paper-100">{t("checkArea.didYouMean")}</p>
            <ul className="divide-y divide-paper-200 dark:divide-night-700">
              {places.map((p) => (
                <li key={`${p.lat},${p.lng}`}>
                  <button type="button" onClick={() => assess(p)} className="flex w-full items-start gap-3 py-3 text-left hover:bg-paper-50 dark:hover:bg-night-800">
                    <MapPin size={18} className="mt-0.5 shrink-0 text-teal-600" />
                    <span>
                      <span className="block text-base font-medium text-ink-900 dark:text-paper-100">{p.name}</span>
                      <span className="block text-xs text-paper-500">{p.detail}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {phase === "done" && result && <Assessment result={result} speech={speech} />}
      </div>
    </DashboardLayout>
  );
}

function Assessment({ result, speech }) {
  const { t } = useTranslation();
  const { place, risk, rain, alertingHere } = result;
  const zone = risk.zone;
  const tier = zone ? zone.tier || "unscored" : null;

  if (!zone) {
    return (
      <div className="rounded-xl border border-paper-200 bg-white p-5 dark:border-night-700 dark:bg-night-900">
        <h2 className="font-serif text-lg font-semibold text-ink-900 dark:text-paper-100">{place.name}</h2>
        <p className="mt-3 text-base font-medium text-ink-900 dark:text-paper-100">{t("checkArea.notFoundTitle")}</p>
        <p className="mt-1 text-sm text-paper-600 dark:text-paper-400">{t("checkArea.notFoundBody")}</p>
        <Emergency className="mt-4" />
      </div>
    );
  }

  const style = TIER_STYLE[tier];
  const Icon = style.icon;
  const advice = t(`checkArea.advice.${tier}`, { returnObjects: true });
  const spoken = [
    place.name,
    t(`checkArea.risk.${tier}`),
    t(`checkArea.meaning.${tier}`, { state: zone.state }),
    ...(Array.isArray(advice) ? advice : []),
    t("checkArea.emergency"),
  ].join(". ");

  return (
    <div className="space-y-4">
      <div className={`rounded-xl border-2 p-5 ${style.box}`}>
        <div className="flex items-start justify-between gap-3">
          <h2 className="font-serif text-lg font-semibold text-ink-900 dark:text-paper-100">
            {place.name}
            {place.detail && <span className="mt-0.5 block text-xs font-normal text-paper-600 dark:text-paper-400">{place.detail}</span>}
          </h2>
          {speech.canSpeak && (
            <button
              type="button"
              onClick={() => (speech.speaking ? speech.stop() : speech.speak(spoken))}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-paper-300 bg-white/70 px-3 py-1.5 text-xs font-medium text-paper-700 dark:bg-night-900/60 dark:text-paper-300"
            >
              {speech.speaking ? <VolumeX size={14} /> : <Volume2 size={14} />}
              {speech.speaking ? t("checkArea.stop") : t("checkArea.listen")}
            </button>
          )}
        </div>

        <div className={`mt-4 flex items-center gap-3 ${style.text}`}>
          <Icon size={44} strokeWidth={1.8} />
          <p className="text-3xl font-bold leading-tight">{t(`checkArea.risk.${tier}`)}</p>
        </div>
        <p className="mt-3 text-base text-ink-900 dark:text-paper-100">{t(`checkArea.meaning.${tier}`, { state: zone.state })}</p>
        <p className="mt-2 text-sm text-paper-600 dark:text-paper-400">
          {t("checkArea.nearestRoad", { km: risk.distanceKm })} · {t("checkArea.nearby", { radius: risk.radiusKm, ...risk.counts })}
        </p>
      </div>

      <div className="rounded-xl border border-paper-200 bg-white p-5 dark:border-night-700 dark:bg-night-900">
        <h3 className="mb-2 font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">{t("checkArea.adviceTitle")}</h3>
        <ul className="space-y-2 text-base text-paper-700 dark:text-paper-300">
          {Array.isArray(advice) && advice.map((line) => (
            <li key={line} className="flex gap-2">
              <span aria-hidden="true">•</span>
              <span>{line}</span>
            </li>
          ))}
        </ul>
        <Emergency className="mt-4" />
      </div>

      <div className="rounded-xl border border-paper-200 bg-white p-5 dark:border-night-700 dark:bg-night-900">
        <h3 className="mb-2 flex items-center gap-2 font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">
          <CloudRain size={18} className="text-teal-600" />
          {t("checkArea.rainTitle")}
        </h3>
        {rain ? (
          <ul className="space-y-1 text-base text-paper-700 dark:text-paper-300">
            {rain.todayMm !== null && (
              <li>{t("checkArea.rainToday", { mm: rain.todayMm.toFixed(1), label: t(`checkArea.rainLabels.${rainClass(rain.todayMm)}`) })}</li>
            )}
            <li>{t("checkArea.rainLast3", { mm: rain.last3Mm.toFixed(1) })}</li>
            <li>{t("checkArea.rainForecast", { mm: rain.forecastMm.toFixed(1) })}</li>
          </ul>
        ) : (
          <p className="text-sm text-paper-500">{t("checkArea.rainUnavailable")}</p>
        )}
        <p className="mt-3 text-sm">
          {risk.activeAlerts > 0 ? (
            <span className="font-medium text-risk-high dark:text-risk-highOn">{t("checkArea.alertActive")}</span>
          ) : alertingHere === true ? (
            <span className="text-paper-600 dark:text-paper-400">{t("checkArea.noAlert")}</span>
          ) : alertingHere === false ? (
            <span className="text-paper-600 dark:text-paper-400">{t("checkArea.alertsOff", { state: zone.state })}</span>
          ) : null}
        </p>
      </div>

      <SurroundingsPanel zoneId={zone.id} />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link to={`/zones/${zone.id}`} className="text-sm font-medium text-teal-600 hover:underline">
          {t("checkArea.viewDetails")}
        </Link>
      </div>

      <p className="text-xs text-paper-500">{t("checkArea.disclaimer")}</p>
    </div>
  );
}

function Emergency({ className = "" }) {
  const { t } = useTranslation();
  return (
    <p className={`flex items-center gap-2 rounded-lg bg-paper-100 px-3 py-2 text-sm font-medium text-ink-900 dark:bg-night-800 dark:text-paper-100 ${className}`}>
      <Phone size={16} className="shrink-0 text-risk-high dark:text-risk-highOn" />
      {t("checkArea.emergency")}
    </p>
  );
}
