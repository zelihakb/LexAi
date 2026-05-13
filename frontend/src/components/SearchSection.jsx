export default function SearchSection({
  question,
  setQuestion,
  handleSearch,
  isLoading,
  loadingText,
  mode,
  canSearch,
  validationMessage,
  exampleChips,
  onExampleClick,
}) {
  return (
    <section className="rounded-[32px] border border-[#C9A227]/8 bg-[#111827]/88 p-6 shadow-2xl shadow-black/40 backdrop-blur md:p-10">
      <div className="mb-4 inline-flex rounded-full border border-[#C9A227]/18 bg-[#C9A227]/8 px-4 py-2 text-sm font-medium text-[#D8B65A]">
        {mode === "ask"
          ? "Hukuki Sorunuzu Yazın"
          : "Karar Arşivinde Arama Yapın"}
      </div>

      <h1 className="max-w-4xl text-4xl font-bold leading-tight tracking-tight text-[#F8FAFC] md:text-6xl">
        Emsal kararları tarayıp düzenli bir sonuç ekranı oluşturalım.
      </h1>

      <p className="mt-4 max-w-3xl text-base leading-8 text-[#CBD5E1] md:text-lg">
        {mode === "ask"
          ? "Doğal dille sorunuzu yazın. Sistem kısa bir yorum oluştursun ve en yakın 5 kararı göstersin."
          : "Anahtar kelime, mahkeme, yıl veya esas-karar numarasıyla karar arşivini filtreleyin."}
      </p>

      <form onSubmit={handleSearch} className="mt-8 flex flex-col gap-4">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={
            mode === "ask"
              ? "Örn: İdari para cezası kesinleşmeden ödeme emri düzenlenebilir mi?"
              : "Örn: Yargıtay 12. HD 2016 icra kararları"
          }
          className="min-h-32 w-full rounded-3xl border border-[#C9A227]/8 bg-[#0B1220] px-5 py-4 text-base text-[#F8FAFC] outline-none transition placeholder:text-[#94A3B8] focus:border-[#C9A227]/28"
        />

        <div className="flex flex-wrap gap-2">
          {exampleChips.map((item, idx) => (
            <button
              key={`${item}-${idx}`}
              type="button"
              onClick={() => onExampleClick(item)}
              className="rounded-full border border-white/8 bg-[#0B1220] px-3 py-2 text-xs text-[#CBD5E1] transition hover:bg-white/5"
            >
              {item}
            </button>
          ))}
        </div>

        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-[#94A3B8]">{validationMessage}</p>

          <button
            type="submit"
            disabled={!canSearch || isLoading}
            className="rounded-full bg-gradient-to-r from-[#C9A227] to-[#D8B65A] px-8 py-3 font-semibold text-[#0B1220] shadow-lg shadow-[#C9A227]/12 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading
              ? "İşleniyor..."
              : mode === "ask"
                ? "Ara ve Yorumla"
                : "Kararları Bul"}
          </button>
        </div>
      </form>

      {isLoading && (
        <div className="mt-6 inline-flex items-center gap-3 rounded-full border border-[#C9A227]/18 bg-[#C9A227]/8 px-4 py-2 text-sm text-[#D8B65A]">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#D8B65A]/20 border-t-[#C9A227]" />
          <span>{loadingText}</span>
        </div>
      )}
    </section>
  );
}
