import DecisionAccordion from "./DecisionAccordion";

export default function ResultsSection({
  mode,
  result,
  filteredItems,
  visibleItems,
  hasSearched,
  summaryText,
}) {
  const items = Array.isArray(filteredItems)
    ? filteredItems
    : Array.isArray(visibleItems)
      ? visibleItems
      : [];

  return (
    <section className="rounded-[32px] border border-[#C9A227]/8 bg-[#111827]/88 p-6 shadow-2xl shadow-black/40 backdrop-blur">
      {mode === "ask" && (
        <>
          <div className="mb-4">
            <h2 className="text-xl font-semibold text-[#D8B65A]">Kısa Yorum</h2>
            <p className="mt-2 text-sm text-[#CBD5E1]">
              Bulunan kararların kısa ve sade değerlendirmesi aşağıdadır. Sonuç
              otomatik taslaktır.
            </p>
          </div>

          <div className="rounded-3xl border border-[#C9A227]/8 bg-[#0B1220] p-5">
            {hasSearched && result?.final_answer ? (
              <p className="whitespace-pre-line leading-8 text-[#F8FAFC]">
                {result.final_answer}
              </p>
            ) : (
              <p className="leading-8 text-[#94A3B8]">
                Sonuç burada görünecek. Önce bir soru yazıp arama yap.
              </p>
            )}
          </div>
        </>
      )}

      {mode === "find" && (
        <div className="mb-6 rounded-3xl border border-[#C9A227]/8 bg-[#0B1220] p-5">
          <h2 className="text-xl font-semibold text-[#D8B65A]">
            Karar Bul Sonucu
          </h2>
          <p className="mt-2 leading-7 text-[#CBD5E1]">
            {hasSearched
              ? summaryText
              : "Arama metni veya filtrelerle karar arşivinde sonuç bulabilirsin."}
          </p>
        </div>
      )}

      <div className={mode === "ask" ? "mt-8" : ""}>
        <div className="mb-4">
          <h2 className="text-xl font-semibold text-[#D8B65A]">
            {mode === "ask" ? "İlk 5 Karar" : "Bulunan Kararlar"}
          </h2>
          <p className="mt-2 text-sm text-[#CBD5E1]">
            Açılır kartlardan karar bilgilerini inceleyebilirsin.
          </p>
        </div>

        <div className="flex flex-col gap-4">
          {hasSearched ? (
            items.length ? (
              items.map((item, index) => (
                <DecisionAccordion
                  key={`${item.payload?.court || "court"}-${item.payload?.case_no || "case"}-${item.payload?.decision_no || "decision"}-${index}`}
                  item={item}
                  index={index}
                />
              ))
            ) : (
              <div className="rounded-3xl border border-dashed border-[#C9A227]/10 bg-[#0B1220] p-6 text-[#94A3B8]">
                Aramana uygun karar bulunamadı. Daha genel kelimeler veya farklı
                filtreler dene.
              </div>
            )
          ) : (
            <div className="rounded-3xl border border-dashed border-[#C9A227]/10 bg-[#0B1220] p-6 text-[#94A3B8]">
              Arama yaptıktan sonra kararlar burada listelenecek.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
