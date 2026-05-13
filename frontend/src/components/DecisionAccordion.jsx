import { useState } from "react";

function getRelationLabel(relation) {
  if (relation === "supports_yes") return "Soruya Evet";
  if (relation === "supports_no") return "Soruya Hayır";
  if (relation === "procedural") return "Usuli";
  if (relation === "irrelevant") return "Zayıf Bağlantı";
  if (relation === "metadata_match") return "Eşleşme";
  return "Net Değil";
}

function normalizeText(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function shouldHideRelevance(summary, relevance) {
  const summaryText = normalizeText(summary);
  const relevanceText = normalizeText(relevance);

  if (!summaryText || !relevanceText) return true;

  if (summaryText === relevanceText) return true;
  if (summaryText.includes(relevanceText)) return true;
  if (relevanceText.includes(summaryText)) return true;

  const genericRelevanceTexts = [
    "bu karar, soruya evet yönünde cevap veren emsaller arasında görülmüştür.",
    "bu karar, soruya hayır yönünde cevap veren emsaller arasında görülmüştür.",
    "bu karar, kullanıcının sorduğu soruya evet cevabını destekler nitelikte değerlendirilmiştir.",
    "bu karar, kullanıcının sorduğu soruya hayır cevabını destekler nitelikte değerlendirilmiştir.",
  ];

  return genericRelevanceTexts.includes(relevanceText);
}

export default function DecisionAccordion({ item, index }) {
  const [open, setOpen] = useState(index === 0);
  const payload = item?.payload ?? {};

  const summary =
    item?.summary || payload.summary || "Bu karar için kısa özet hazırlanmadı.";

  const relevance =
    item?.relevance ||
    payload.relevance ||
    "Bu karar, arama sonucu içinde eşleşen emsal kararlardan biridir.";

  const relation = item?.relation || payload.relation || "";

  const showRelevance = !shouldHideRelevance(summary, relevance);

  return (
    <div className="overflow-hidden rounded-3xl border border-[#C9A227]/8 bg-[#0B1220]">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition hover:bg-white/4"
      >
        <div className="flex items-center gap-4">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#C9A227]/10 font-semibold text-[#D8B65A]">
            {index + 1}
          </div>

          <div>
            <h3 className="text-base font-semibold text-[#F8FAFC]">
              {payload.court || "Karar"}
            </h3>
            <p className="text-sm text-[#CBD5E1]">
              E. {payload.case_no || "-"} • K. {payload.decision_no || "-"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {relation && (
            <span className="hidden rounded-full border border-[#C9A227]/10 bg-[#C9A227]/8 px-3 py-1 text-xs font-medium text-[#D8B65A] md:inline">
              {getRelationLabel(relation)}
            </span>
          )}

          <span
            className={`text-xl text-[#D8B65A] transition-transform ${
              open ? "rotate-180" : ""
            }`}
          >
            ⌄
          </span>
        </div>
      </button>

      {open && (
        <div className="border-t border-[#C9A227]/8 px-5 pb-5 pt-4">
          <div className="mb-4 flex flex-wrap gap-6 text-sm text-[#CBD5E1]">
            <div className="flex flex-col gap-1">
              <span className="text-xs uppercase tracking-wide text-[#D8B65A]">
                Mahkeme
              </span>
              <span>{payload.court || "-"}</span>
            </div>

            <div className="flex flex-col gap-1">
              <span className="text-xs uppercase tracking-wide text-[#D8B65A]">
                Esas No
              </span>
              <span>{payload.case_no || "-"}</span>
            </div>

            <div className="flex flex-col gap-1">
              <span className="text-xs uppercase tracking-wide text-[#D8B65A]">
                Karar No
              </span>
              <span>{payload.decision_no || "-"}</span>
            </div>

            <div className="flex flex-col gap-1">
              <span className="text-xs uppercase tracking-wide text-[#D8B65A]">
                Tarih
              </span>
              <span>{payload.decision_date || "-"}</span>
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-2xl border border-[#C9A227]/8 bg-[#111827]/70 p-4">
              <h4 className="mb-2 text-sm font-semibold text-[#D8B65A]">
                Bu Karar Ne Anlama Geliyor?
              </h4>
              <p className="whitespace-pre-line leading-7 text-[#F8FAFC]">
                {summary}
              </p>
            </div>

            {showRelevance && (
              <div className="rounded-2xl border border-[#C9A227]/8 bg-[#111827]/70 p-4">
                <h4 className="mb-2 text-sm font-semibold text-[#D8B65A]">
                  Soruyla Bağlantısı
                </h4>
                <p className="leading-7 text-[#F8FAFC]">{relevance}</p>
              </div>
            )}

            <p className="text-xs leading-6 text-[#94A3B8]">
              Not: Bu özet yapay zekâ tarafından hazırlanmıştır; hukuki
              danışmanlık niteliği taşımaz.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
