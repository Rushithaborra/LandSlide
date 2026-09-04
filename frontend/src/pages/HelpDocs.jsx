import DashboardLayout from "../layouts/DashboardLayout";

const faqs = [
  {
    q: "Where does the data on this dashboard come from?",
    a: "Rainfall comes from IMD and Open-Meteo. Terrain and susceptibility scoring come from DEM rasters, GSI landslide records, and Sentinel-2 imagery, processed through the GIS pipeline described in the project README.",
  },
  {
    q: "How is a zone marked High / Moderate / Low risk?",
    a: "A machine-learning classifier produces a baseline susceptibility score, which is then combined with a live rainfall-intensity/duration rule engine to produce the final risk level shown on the map and alerts.",
  },
  {
    q: "Can residents submit their own reports?",
    a: "Yes — see the Citizen Reports page. Reports are stored with their location and, once the PWA photo-upload backend is connected, an attached photo.",
  },
];

export default function HelpDocs() {
  return (
    <DashboardLayout title="Help & Docs" subtitle="Frequently asked questions and documentation">
      <div className="bg-white rounded-xl border border-paper-200 p-4 divide-y divide-paper-200 max-w-2xl">
        {faqs.map((f) => (
          <div key={f.q} className="py-4 first:pt-0 last:pb-0">
            <p className="text-sm font-medium text-ink-800">{f.q}</p>
            <p className="text-sm text-paper-600 mt-1 leading-relaxed">{f.a}</p>
          </div>
        ))}
      </div>
    </DashboardLayout>
  );
}
