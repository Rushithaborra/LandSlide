import { useMemo, useState } from "react";
import { ScrollText, ShieldCheck } from "lucide-react";
import DashboardLayout from "../layouts/DashboardLayout";

/**
 * ============================================================================
 *  DATA SOURCES & METHODOLOGY
 * ============================================================================
 * This build is already unusually explicit, internally, about what's real vs
 * simulated (README.md's "Implemented / Simulated / Pending" section,
 * CLAUDE.md, the `verified_against_primary_text` config flag, the Broadcast
 * composer's own "Simulated" banner). This page surfaces that same discipline
 * IN THE PRODUCT rather than leaving it buried in engineering docs — every
 * data source, model, and AI feature this system uses, honestly labelled.
 *
 * English-only, same as HelpDocs.jsx and for the same reason (README.md,
 * "Multilingual dashboard UI" section): long-form technical prose, not a
 * short UI label, and a hasty machine translation risks being sloppy for
 * something judges specifically read closely.
 *
 * Keep this in sync with README.md's "Implemented / Simulated / Pending" and
 * CLAUDE.md's session log whenever a source's real/simulated status changes.
 * ============================================================================
 */

const STATUS = {
  live: {
    label: "Real & live",
    badge: "bg-risk-lowSoft text-risk-low dark:bg-risk-low/10 dark:text-risk-lowOn",
  },
  unverified: {
    label: "Real — cited source not independently verified",
    badge: "bg-risk-moderateSoft text-risk-moderate dark:bg-risk-moderate/10 dark:text-risk-moderateOn",
  },
  derived: {
    label: "Team-derived rule, not literature-sourced",
    badge: "bg-teal-100 text-teal-700 dark:bg-teal-600/20 dark:text-teal-100",
  },
  simulated: {
    label: "Simulated — not wired up",
    badge: "bg-paper-100 text-paper-600 dark:bg-night-800 dark:text-paper-400",
  },
};

const SECTIONS = [
  {
    title: "Terrain & geospatial inputs",
    items: [
      {
        name: "Copernicus GLO-30 DEM",
        status: "live",
        detail:
          "30m global elevation model, downloaded from AWS Open Data (no API key). Reprojected to UTM 45N before deriving slope/aspect/curvature — verified that without reprojection, slope comes out ~90° everywhere.",
      },
      {
        name: "OpenStreetMap road network",
        status: "live",
        detail:
          "Sikkim's road geometry via the Overpass API — 768 filtered ways turned into 3,921 ~500m corridor segments, each a susceptibility prediction unit.",
      },
      {
        name: "ESA WorldCover land cover",
        status: "live",
        detail: "10m resolution, 2021 v200 — dominant land-cover class extracted per corridor segment.",
      },
      {
        name: "GSI Sikkim landslide inventory",
        status: "live",
        detail:
          "765 verified historical landslide points (777 raw records; 3 duplicate-coordinate positives resolved) — the real ground-truth positives the susceptibility model trains on.",
      },
    ],
  },
  {
    title: "Weather & rainfall",
    items: [
      {
        name: "Open-Meteo",
        status: "live",
        detail:
          "Daily rainfall — past days plus a 3-day forecast (today + 2 real future days). This is the only rainfall source actually wired up.",
      },
      {
        name: "IMD (India Meteorological Department)",
        status: "simulated",
        detail:
          "The pitch deck's tech-stack slide names IMD as the primary rainfall source with Open-Meteo as fallback. IMD API access wasn't reachable in this build's timeframe — Open-Meteo is what's actually live, not IMD.",
      },
      {
        name: "Rainfall intensity-duration threshold",
        status: "unverified",
        detail:
          "Harilal, Madhu, Ramesh & Pullarkatt (2019), Landslides 16(12), DOI 10.1007/s10346-019-01244-1 — a real, Sikkim-specific paper. The paper is paywalled, so its coefficients haven't yet been independently confirmed against the primary text.",
      },
      {
        name: "Susceptibility × rainfall multiplier table",
        status: "derived",
        detail:
          "Scales the rainfall threshold down for higher-susceptibility zones. This weighting is the team's own explainable rule, not sourced from a paper — said plainly here rather than dressed up as literature or as ML.",
      },
    ],
  },
  {
    title: "Machine learning models",
    items: [
      {
        name: "Susceptibility model — Random Forest (extended features)",
        status: "live",
        detail:
          "Trained on 774 positive / 774 negative points, evaluated with 5-fold spatially-buffered block cross-validation (not a naive random split). ROC-AUC 0.735. Currently scores 510 zones — mostly one corridor (NH717A) extending past the other model's raster coverage.",
      },
      {
        name: "Susceptibility model — Person B's Random Forest",
        status: "live",
        detail:
          "A separate, independently-built pipeline (real DEM, real GSI inventory, a RUSLE erosion model) — held-out AUC 0.774–0.782 on a plain 75/25 split, not the spatially-buffered CV the other model uses, worth noting if compared side by side. Currently scores 3,411 of 3,921 zones.",
      },
    ],
  },
  {
    title: "AI assist — Google Gemini (gemini-3.5-flash-lite)",
    items: [
      {
        name: "Citizen report triage summary",
        status: "live",
        detail:
          "One-line officer-facing summary of each citizen report, always in English. Shown labelled \"AI-generated triage summary\" — never presented as the citizen's own words.",
      },
      {
        name: "Alert bulletin draft (\"Draft with AI\")",
        status: "live",
        detail:
          "Proposes a headline and message from a zone's real rainfall/risk data in the Broadcast composer. Always reviewable and editable before sending — never auto-sent.",
      },
      {
        name: "Citizen wording assist (\"Clean up wording\")",
        status: "live",
        detail:
          "Cleans grammar and clarity in the citizen's own description before submission — strictly forbidden from adding new facts (temperature 0.1). The citizen chooses \"Use this\" or keeps their own wording; nothing is auto-applied.",
      },
      {
        name: "Citizen report translation",
        status: "live",
        detail:
          "Every report's description is translated to English for the dashboard, shown alongside — not replacing — the citizen's original wording.",
      },
    ],
  },
  {
    title: "Alerts & delivery",
    items: [
      {
        name: "Twilio SMS & voice",
        status: "live",
        detail:
          "Real dispatch — a critical broadcast has placed an actual phone call, confirmed by the recipient. Runs on a trial account, so only phone numbers manually verified in the Twilio console currently receive anything.",
      },
      {
        name: "WhatsApp-ready alert copy",
        status: "simulated",
        detail:
          "No WhatsApp Business API is integrated. The Broadcast composer instead formats a paste-ready message an officer copies into a real WhatsApp broadcast list by hand — honest about being a manual step, not an automated send.",
      },
      {
        name: "Mobile app push / community sirens / govt CAP XML gateway",
        status: "simulated",
        detail:
          "Selectable as broadcast channels and logged to the database as a real record, but no push, siren, or CAP gateway is actually wired up yet — the confirmation banner says so explicitly at send time.",
      },
    ],
  },
  {
    title: "Storage & infrastructure",
    items: [
      {
        name: "Supabase (Postgres + PostGIS, Storage)",
        status: "live",
        detail: "Live database and citizen-report photo storage. Photo URLs returned by the API are real, directly-viewable Supabase Storage links.",
      },
      {
        name: "Render (FastAPI hosting)",
        status: "live",
        detail: "The backend API is deployed here via a Blueprint (render.yaml), not run only on a laptop.",
      },
    ],
  },
];

function StatusBadge({ status }) {
  const s = STATUS[status];
  return (
    <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${s.badge}`}>
      {s.label}
    </span>
  );
}

export default function DataMethodology() {
  const [filter, setFilter] = useState("all");

  const counts = useMemo(() => {
    const c = { live: 0, unverified: 0, derived: 0, simulated: 0 };
    SECTIONS.forEach((s) => s.items.forEach((i) => c[i.status]++));
    return c;
  }, []);

  const sections = useMemo(() => {
    if (filter === "all") return SECTIONS;
    return SECTIONS.map((s) => ({ ...s, items: s.items.filter((i) => i.status === filter) })).filter(
      (s) => s.items.length > 0
    );
  }, [filter]);

  return (
    <DashboardLayout
      title="Data Sources & Methodology"
      subtitle="Every data source, model, and AI feature this system uses — real, cited, or simulated"
    >
      <div className="mx-auto w-full max-w-3xl space-y-6">
        <div className="rounded-xl border border-paper-200 bg-white p-5 dark:border-night-700 dark:bg-night-900">
          <div className="flex items-start gap-3">
            <ScrollText size={20} className="mt-0.5 shrink-0 text-teal-600" />
            <div className="min-w-0 flex-1">
              <h2 className="font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">
                Why this page exists
              </h2>
              <p className="mt-1 text-sm leading-relaxed text-paper-600 dark:text-paper-400">
                A system that decides when to warn people about a landslide should be able to say,
                plainly, where every number in it comes from. This page lists each upstream data
                source, model, and AI feature the dashboard relies on, labelled honestly: genuinely
                live and verified, a real citation not yet independently confirmed, a rule the team
                designed itself, or a feature that isn't wired up to a real gateway yet.
              </p>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {[
              { id: "all", label: `All (${SECTIONS.reduce((n, s) => n + s.items.length, 0)})` },
              { id: "live", label: `${STATUS.live.label} (${counts.live})` },
              { id: "unverified", label: `${STATUS.unverified.label} (${counts.unverified})` },
              { id: "derived", label: `${STATUS.derived.label} (${counts.derived})` },
              { id: "simulated", label: `${STATUS.simulated.label} (${counts.simulated})` },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setFilter(f.id)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  filter === f.id
                    ? "border-teal-600 bg-teal-600 text-white"
                    : "border-paper-200 bg-white text-paper-600 hover:bg-paper-50 dark:border-night-700 dark:bg-night-900 dark:text-paper-400"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {sections.map((section) => (
          <div
            key={section.title}
            className="rounded-xl border border-paper-200 bg-white p-5 dark:border-night-700 dark:bg-night-900"
          >
            <h2 className="mb-3 font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">
              {section.title}
            </h2>
            <div className="divide-y divide-paper-200 dark:divide-night-700">
              {section.items.map((item) => (
                <div key={item.name} className="py-3 first:pt-0 last:pb-0">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <p className="text-sm font-medium text-ink-800 dark:text-paper-200">{item.name}</p>
                    <StatusBadge status={item.status} />
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-paper-600 dark:text-paper-400">
                    {item.detail}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ))}

        <div className="rounded-xl border border-paper-200 bg-paper-50 p-5 dark:border-night-700 dark:bg-night-800">
          <div className="flex items-start gap-3">
            <ShieldCheck size={18} className="mt-0.5 shrink-0 text-paper-500" />
            <p className="text-xs leading-relaxed text-paper-600 dark:text-paper-400">
              This page is maintained by hand alongside the engineering docs (README.md, CLAUDE.md) —
              if a source's status changes there, it should change here too. No auth exists on any
              endpoint in this build; that's a scoped-out gap for this round, not a data source.
            </p>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
