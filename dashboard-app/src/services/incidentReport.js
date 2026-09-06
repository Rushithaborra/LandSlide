import { jsPDF } from "jspdf";

/**
 * ============================================================================
 *  INCIDENT REPORT PDF GENERATOR  (NEW IN DRAFT 3)
 * ============================================================================
 * This is what the old "Reports" page was supposed to do. It now lives on the
 * Incidents page: every incident row has a "Download" button in the last
 * column, and pressing it builds and saves a PDF for that one incident.
 *
 * The PDF contains, in order:
 *   1. Incident ID, location, area, date, severity, status
 *   2. Weather report at the time of the event
 *   3. Rainfall trend leading up to the event (table + simple bar chart)
 *   4. Previous recorded activity in that area (history)
 *   5. Impact and response summary
 *   6. Every citizen report filed from the same area
 *
 * Everything is generated in the browser with jsPDF (free, MIT licensed).
 * No server and no internet connection are needed.
 *
 * See LINK SPOT L in src/services/api.js if the team later wants the PDF
 * rendered server-side instead.
 * ============================================================================
 */

// ---- page geometry, in millimetres (A4 is 210 x 297) ----
const M = 16; // page margin
const W = 210;
const H = 297;
const CONTENT = W - M * 2;

// ---- palette, matching the dashboard ----
const INK = [38, 51, 46];
const TERRA = [180, 71, 47];
const TURMERIC = [200, 135, 29];
const MOSS = [91, 140, 79];
const MUTED = [107, 100, 89];
const RULE = [215, 208, 190];

const severityColor = (s) =>
  s === "High" ? TERRA : s === "Moderate" ? TURMERIC : MOSS;

export function generateIncidentReport(incident, relatedReports = []) {
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  let y = M;

  // ------------------------------------------------------------------ utils
  const newPageIfNeeded = (needed = 12) => {
    if (y + needed > H - M) {
      doc.addPage();
      y = M;
    }
  };

  const rule = () => {
    doc.setDrawColor(...RULE);
    doc.setLineWidth(0.3);
    doc.line(M, y, W - M, y);
    y += 5;
  };

  const heading = (text) => {
    newPageIfNeeded(16);
    y += 3;
    doc.setFont("helvetica", "bold");
    doc.setFontSize(11.5);
    doc.setTextColor(...TERRA);
    doc.text(text.toUpperCase(), M, y);
    y += 2.5;
    rule();
  };

  const para = (text, { size = 9.5, color = INK, gap = 4.2 } = {}) => {
    doc.setFont("helvetica", "normal");
    doc.setFontSize(size);
    doc.setTextColor(...color);
    const lines = doc.splitTextToSize(text, CONTENT);
    lines.forEach((line) => {
      newPageIfNeeded(6);
      doc.text(line, M, y);
      y += gap;
    });
  };

  const field = (label, value) => {
    newPageIfNeeded(7);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(9);
    doc.setTextColor(...MUTED);
    doc.text(label, M, y);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9.5);
    doc.setTextColor(...INK);
    const lines = doc.splitTextToSize(String(value ?? "—"), CONTENT - 48);
    doc.text(lines, M + 48, y);
    y += Math.max(5.6, lines.length * 4.6);
  };

  // ----------------------------------------------------------------- header
  doc.setFillColor(...INK);
  doc.rect(0, 0, W, 26, "F");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(13);
  doc.setTextColor(245, 242, 234);
  doc.text("Landslide Early Warning System", M, 12);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(179, 171, 153);
  doc.text("Incident Report — generated from the Incidents dashboard", M, 18.5);
  doc.setFontSize(8);
  doc.text(
    `Generated ${new Date().toLocaleString("en-IN")}`,
    W - M,
    18.5,
    { align: "right" }
  );
  y = 36;

  // ------------------------------------------------------------ incident id
  doc.setFont("helvetica", "bold");
  doc.setFontSize(17);
  doc.setTextColor(...INK);
  doc.text(`${incident.id} — ${incident.location}`, M, y);
  y += 7;

  // severity chip
  const sev = severityColor(incident.severity);
  doc.setFillColor(...sev);
  doc.roundedRect(M, y - 3.6, 26, 5.6, 1.2, 1.2, "F");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(8);
  doc.setTextColor(255, 255, 255);
  doc.text(`${incident.severity} risk`.toUpperCase(), M + 13, y, {
    align: "center",
  });
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(...MUTED);
  doc.text(`Status: ${incident.status}`, M + 30, y);
  y += 8;
  rule();

  // --------------------------------------------------------------- 1. facts
  heading("1. Incident details");
  field("Incident ID", incident.id);
  field("Location", incident.location);
  field("Area", incident.area);
  field("Date of event", incident.date);
  field("Severity", incident.severity);
  field("Status", incident.status);
  field("Casualties", incident.casualties);
  field("Infrastructure impact", incident.infrastructureImpact);

  // ------------------------------------------------------------- 2. weather
  heading("2. Weather report");
  para(incident.weatherReport || "No weather record attached.");

  // ------------------------------------------------------ 3. rainfall trend
  heading("3. Rainfall trend leading to the event");
  const trend = incident.rainfallTrend || [];
  if (trend.length) {
    const peak = Math.max(...trend.map((d) => d.mm), 1);
    const barW = 26;
    const gap = 4;
    const chartH = 30;
    newPageIfNeeded(chartH + 18);
    const baseY = y + chartH;

    trend.forEach((d, i) => {
      const x = M + i * (barW + gap);
      const h = Math.max(1.5, (d.mm / peak) * chartH);
      // bars above the 100 mm trigger threshold are drawn in terracotta
      const c = d.mm >= 100 ? TERRA : [126, 166, 172];
      doc.setFillColor(...c);
      doc.rect(x, baseY - h, barW, h, "F");

      doc.setFont("helvetica", "bold");
      doc.setFontSize(7.5);
      doc.setTextColor(...INK);
      doc.text(`${d.mm} mm`, x + barW / 2, baseY - h - 1.8, { align: "center" });

      doc.setFont("helvetica", "normal");
      doc.setFontSize(7.5);
      doc.setTextColor(...MUTED);
      doc.text(d.day, x + barW / 2, baseY + 4, { align: "center" });
    });

    // 100 mm threshold line
    const thY = baseY - (100 / peak) * chartH;
    if (thY > y) {
      doc.setDrawColor(...TERRA);
      doc.setLineDashPattern([1.2, 1.2], 0);
      doc.line(M, thY, M + trend.length * (barW + gap) - gap, thY);
      doc.setLineDashPattern([], 0);
      doc.setFontSize(7);
      doc.setTextColor(...TERRA);
      doc.text("100 mm trigger threshold", M, thY - 1.5);
    }
    y = baseY + 10;
  } else {
    para("No rainfall series attached to this incident.");
  }

  // ----------------------------------------------------- 4. previous record
  heading("4. Previous recorded activity in this area");
  const history = incident.areaHistory || [];
  if (history.length) {
    history.forEach((h) => {
      newPageIfNeeded(8);
      doc.setFillColor(...MUTED);
      doc.circle(M + 1.2, y - 1.4, 0.9, "F");
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9.5);
      doc.setTextColor(...INK);
      const lines = doc.splitTextToSize(h, CONTENT - 6);
      doc.text(lines, M + 5, y);
      y += Math.max(5.2, lines.length * 4.4);
    });
  } else {
    para("No earlier records for this area.");
  }

  // ------------------------------------------------------------- 5. response
  heading("5. Response summary");
  para(incident.responseSummary || "No response record attached.");

  // ------------------------------------------------------ 6. citizen reports
  heading(`6. Citizen reports from ${incident.area || "this area"}`);
  if (relatedReports.length) {
    relatedReports.forEach((r) => {
      newPageIfNeeded(30);
      doc.setDrawColor(...RULE);
      doc.setLineWidth(0.3);
      doc.roundedRect(M, y - 4, CONTENT, 25, 1.5, 1.5, "S");

      doc.setFont("helvetica", "bold");
      doc.setFontSize(9.5);
      doc.setTextColor(...INK);
      doc.text(`${r.id} — ${r.location}`, M + 3, y + 1);

      const rc = r.status === "Verified" ? MOSS : TURMERIC;
      doc.setFontSize(8);
      doc.setTextColor(...rc);
      doc.text(r.status, W - M - 3, y + 1, { align: "right" });

      doc.setFont("helvetica", "normal");
      doc.setFontSize(8.5);
      doc.setTextColor(...MUTED);
      doc.text(
        `${r.reporterName || r.reporter} · ${r.reporterType || "Citizen"} · ${r.submittedAt}`,
        M + 3,
        y + 6
      );

      doc.setFontSize(9);
      doc.setTextColor(...INK);
      const note = doc.splitTextToSize(r.note, CONTENT - 6);
      doc.text(note.slice(0, 2), M + 3, y + 11.5);

      doc.setFontSize(8);
      doc.setTextColor(...MUTED);
      doc.text(
        `Coordinates ${r.lat}, ${r.lng}${r.landmark ? " · " + r.landmark : ""}`,
        M + 3,
        y + 18.5
      );

      y += 29;
    });
  } else {
    para("No citizen reports were filed from this area.");
  }

  // ----------------------------------------------------------- page footers
  const pages = doc.getNumberOfPages();
  for (let i = 1; i <= pages; i += 1) {
    doc.setPage(i);
    doc.setDrawColor(...RULE);
    doc.line(M, H - 12, W - M, H - 12);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(7.5);
    doc.setTextColor(...MUTED);
    doc.text(
      "Landslide Early Warning System · Data sources: IMD, GSI, ISRO, Open-Meteo",
      M,
      H - 8
    );
    doc.text(`Page ${i} of ${pages}`, W - M, H - 8, { align: "right" });
  }

  doc.save(`${incident.id}_${(incident.location || "incident").split(",")[0].replace(/\s+/g, "_")}_report.pdf`);
}
