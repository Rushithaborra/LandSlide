import DashboardLayout from "../layouts/DashboardLayout";

export default function Settings() {
  return (
    <DashboardLayout title="Settings" subtitle="Account and system preferences">
      <div className="bg-white rounded-xl border border-paper-200 p-6 max-w-lg space-y-4">
        <div>
          <label className="text-xs text-paper-600">Display name</label>
          <input
            defaultValue="Admin"
            className="w-full mt-1 rounded-lg border border-paper-200 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="text-xs text-paper-600">Alert threshold region</label>
          <select className="w-full mt-1 rounded-lg border border-paper-200 px-3 py-2 text-sm">
            <option>Sikkim</option>
            <option>Uttarakhand</option>
            <option>Kerala</option>
          </select>
        </div>
        <p className="text-xs text-paper-500">
          TODO: connect these fields to a real user-settings endpoint once
          authentication (Stage — not yet in the pipeline diagram) is added.
        </p>
      </div>
    </DashboardLayout>
  );
}
