export default function ModeToggle({ mode, setMode }) {
  return (
    <div className="inline-flex rounded-full border border-[#C9A227]/12 bg-[#111827]/90 p-1 shadow-lg shadow-black/20">
      <button
        onClick={() => setMode("ask")}
        className={`rounded-full px-4 py-2 text-sm font-medium transition ${
          mode === "ask"
            ? "bg-[#C9A227] text-[#0B1220]"
            : "text-[#CBD5E1] hover:bg-white/5"
        }`}
      >
        Soru Sor
      </button>

      <button
        onClick={() => setMode("find")}
        className={`rounded-full px-4 py-2 text-sm font-medium transition ${
          mode === "find"
            ? "bg-[#C9A227] text-[#0B1220]"
            : "text-[#CBD5E1] hover:bg-white/5"
        }`}
      >
        Karar Bul
      </button>
    </div>
  );
}
