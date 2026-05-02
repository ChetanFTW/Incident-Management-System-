const colors = {
  P0: "bg-red-600 text-white",
  P1: "bg-orange-500 text-white",
  P2: "bg-yellow-400 text-black",
};

export default function PriorityBadge({ priority }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-bold ${colors[priority] || "bg-gray-600 text-white"}`}>
      {priority}
    </span>
  );
}
