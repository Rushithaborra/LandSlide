export default function LoadError({ message, onRetry }) {
  return (
    <div className="rounded-xl border border-risk-high/30 bg-risk-highSoft dark:bg-risk-high/10 p-5">
      <p className="text-sm font-medium text-risk-high">Couldn't load this page</p>
      <p className="text-sm text-paper-500 mt-1">{message}</p>
      <button
        onClick={onRetry}
        className="mt-3 text-sm font-medium px-3 py-1.5 rounded-lg bg-risk-high text-white hover:opacity-90"
      >
        Retry
      </button>
    </div>
  );
}
