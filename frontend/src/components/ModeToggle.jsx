export default function ModeToggle({ mode, setMode }) {
  const tabs = [
    { key: "ask", label: "Soru Sor" },
    { key: "find", label: "Karar Bul" },
    { key: "document", label: "Belge Oku" },
    { key: "petition", label: "Dilekçe" },
  ];

  return (
    <div className="inline-flex flex-wrap justify-center rounded-full border border-[#C9A227]/12 bg-[#111827]/90 p-1 shadow-lg shadow-black/20">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => setMode(tab.key)}
          className={`rounded-full px-4 py-2 text-sm font-medium transition ${
            mode === tab.key
              ? "bg-[#C9A227] text-[#0B1220]"
              : "text-[#CBD5E1] hover:bg-white/5"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}