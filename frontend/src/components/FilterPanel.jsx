export default function FilterPanel({
  filters,
  setFilters,
  mode,
  clearFilters,
}) {
  if (mode !== "find") return null;

  const updateFilter = (key, value) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  return (
    <aside className="h-fit rounded-[28px] border border-[#C9A227]/8 bg-[#111827]/88 p-5 shadow-2xl shadow-black/30">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-lg font-semibold text-[#D8B65A]">Filtreleme</h3>
        <button
          type="button"
          onClick={clearFilters}
          className="rounded-full border border-white/8 px-3 py-1.5 text-xs text-[#CBD5E1] transition hover:bg-white/5"
        >
          Temizle
        </button>
      </div>

      <p className="mt-2 text-sm leading-6 text-[#CBD5E1]">
        Karar Bul modunda mahkeme, yıl, esas no veya karar no ile exact arama
        yapabilirsin.
      </p>

      <div className="mt-5 space-y-4">
        <div>
          <label className="mb-2 block text-sm text-[#D8B65A]">Esas No</label>
          <input
            value={filters.case_no}
            onChange={(e) => updateFilter("case_no", e.target.value)}
            placeholder="Örn: 2024/11216"
            className="w-full rounded-2xl border border-[#C9A227]/8 bg-[#0B1220] px-4 py-3 text-sm text-[#F8FAFC] outline-none placeholder:text-[#94A3B8] focus:border-[#C9A227]/28"
          />
        </div>

        <div>
          <label className="mb-2 block text-sm text-[#D8B65A]">Karar No</label>
          <input
            value={filters.decision_no}
            onChange={(e) => updateFilter("decision_no", e.target.value)}
            placeholder="Örn: 2024/11216"
            className="w-full rounded-2xl border border-[#C9A227]/8 bg-[#0B1220] px-4 py-3 text-sm text-[#F8FAFC] outline-none placeholder:text-[#94A3B8] focus:border-[#C9A227]/28"
          />
        </div>

        <div>
          <label className="mb-2 block text-sm text-[#D8B65A]">Mahkeme</label>
          <input
            value={filters.court}
            onChange={(e) => updateFilter("court", e.target.value)}
            placeholder="Örn: Yargıtay 12. Hukuk Dairesi"
            className="w-full rounded-2xl border border-[#C9A227]/8 bg-[#0B1220] px-4 py-3 text-sm text-[#F8FAFC] outline-none placeholder:text-[#94A3B8] focus:border-[#C9A227]/28"
          />
        </div>

        <div>
          <label className="mb-2 block text-sm text-[#D8B65A]">Yıl</label>
          <input
            value={filters.year}
            onChange={(e) => updateFilter("year", e.target.value)}
            placeholder="Örn: 2024"
            className="w-full rounded-2xl border border-[#C9A227]/8 bg-[#0B1220] px-4 py-3 text-sm text-[#F8FAFC] outline-none placeholder:text-[#94A3B8] focus:border-[#C9A227]/28"
          />
        </div>
      </div>
    </aside>
  );
}
