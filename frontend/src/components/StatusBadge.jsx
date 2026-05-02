const colors = {
  OPEN:          "bg-red-900 text-red-300 border border-red-700",
  INVESTIGATING: "bg-yellow-900 text-yellow-300 border border-yellow-700",
  RESOLVED:      "bg-blue-900 text-blue-300 border border-blue-700",
  CLOSED:        "bg-green-900 text-green-300 border border-green-700",
};

export default function StatusBadge({ status }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${colors[status] || ""}`}>
      {status}
    </span>
  );
}
