import { useMemo, useState } from "react";

const fieldClass =
  "w-full rounded-2xl border border-[#C9A227]/8 bg-[#0B1220] px-4 py-3 text-sm text-[#F8FAFC] outline-none placeholder:text-[#94A3B8] focus:border-[#C9A227]/28";

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export default function PetitionSection({
  form,
  setForm,
  handlePetitionSubmit,
  isLoading,
  result,
}) {
  const [copied, setCopied] = useState(false);

  const canSubmit = useMemo(() => {
    return (
      form.event_summary.trim().length >= 10 &&
      form.request_summary.trim().length >= 5
    );
  }, [form]);

  const updateField = (key, value) => {
    setForm((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const copyPetition = async () => {
    const text = result?.petition_text || "";
    if (!text) return;

    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  };

  const exportAsPdf = () => {
    const text = result?.petition_text || "";
    if (!text) return;

    const popup = window.open("", "_blank", "width=900,height=700");

    if (!popup) {
      window.alert(
        "PDF penceresi açılamadı. Tarayıcı popup iznini kontrol et.",
      );
      return;
    }

    const safeText = escapeHtml(text);

    popup.document.open();
    popup.document.write(`
      <!doctype html>
      <html lang="tr">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>Dilekçe Taslağı</title>

          <style>
            @page {
              size: A4;
              margin: 24mm 20mm;
            }

            * {
              box-sizing: border-box;
            }

            html,
            body {
              margin: 0;
              padding: 0;
              background: #ffffff;
            }

            body {
              font-family: Arial, "Times New Roman", sans-serif;
              color: #111827;
              line-height: 1.6;
              font-size: 12pt;
            }

            .toolbar {
              position: sticky;
              top: 0;
              z-index: 10;
              display: flex;
              justify-content: space-between;
              align-items: center;
              gap: 12px;
              padding: 12px 16px;
              margin: 0 0 20px;
              background: #111827;
              color: #ffffff;
              font-family: Arial, sans-serif;
            }

            .toolbar-title {
              font-size: 13px;
              font-weight: 700;
              letter-spacing: 0.02em;
            }

            .toolbar button {
              border: 0;
              border-radius: 999px;
              background: #C9A227;
              color: #111827;
              padding: 8px 14px;
              font-weight: 700;
              cursor: pointer;
            }

            main {
              max-width: 760px;
              margin: 0 auto;
              padding: 0 8px 24px;
            }

            .document {
              white-space: pre-wrap;
              word-break: break-word;
            }

            .note {
              margin-top: 32px;
              padding-top: 12px;
              border-top: 1px solid #d1d5db;
              color: #6b7280;
              font-size: 9pt;
              line-height: 1.5;
            }

            @media print {
              html,
              body {
                margin: 0 !important;
                padding: 0 !important;
                background: #ffffff !important;
              }

              .no-print,
              .toolbar {
                display: none !important;
                visibility: hidden !important;
                height: 0 !important;
                overflow: hidden !important;
              }

              main {
                max-width: none !important;
                margin: 0 !important;
                padding: 0 !important;
              }

              .document {
                white-space: pre-wrap !important;
              }

              .note {
                break-inside: avoid;
              }
            }
          </style>
        </head>

        <body>
          <div class="toolbar no-print">
            <span class="toolbar-title">LexAI Dilekçe Taslağı</span>
            <button type="button" onclick="window.print()">PDF Olarak Kaydet</button>
          </div>

          <main>
            <div class="document">${safeText}</div>

            <div class="note">
              Bu metin LexAI tarafından yapay zekâ ile oluşturulmuş bir taslaktır.
              Hukuki danışmanlık niteliği taşımaz. Kullanılmadan önce somut olay,
              güncel mevzuat ve uzman hukukçu değerlendirmesiyle kontrol edilmelidir.
            </div>
          </main>

          <script>
            window.onload = function () {
              window.focus();
              setTimeout(function () {
                window.print();
              }, 500);
            };
          </script>
        </body>
      </html>
    `);

    popup.document.close();
  };

  return (
    <section className="grid gap-6 lg:grid-cols-[420px_minmax(0,1fr)]">
      <div className="h-fit rounded-[32px] border border-[#C9A227]/8 bg-[#111827]/88 p-6 shadow-2xl shadow-black/40 backdrop-blur">
        <div className="mb-4 inline-flex rounded-full border border-[#C9A227]/18 bg-[#C9A227]/8 px-4 py-2 text-sm font-medium text-[#D8B65A]">
          Dilekçe Yardımı
        </div>

        <h1 className="text-3xl font-bold leading-tight tracking-tight text-[#F8FAFC] md:text-4xl">
          Bilgileri yaz, dilekçe taslağını oluşturalım.
        </h1>

        <p className="mt-3 text-sm leading-7 text-[#CBD5E1]">
          Bu alan Gemini API ile gerçek dilekçe taslağı üretir. Eksik bilgiler
          varsa taslakta boşluk bırakılır.
        </p>

        <form onSubmit={handlePetitionSubmit} className="mt-6 space-y-4">
          <div>
            <label className="mb-2 block text-sm text-[#D8B65A]">
              Dilekçe Türü
            </label>
            <input
              value={form.petition_type}
              onChange={(e) => updateField("petition_type", e.target.value)}
              placeholder="Örn: İhtiyaç nedeniyle tahliye dilekçesi"
              className={fieldClass}
            />
          </div>

          <div>
            <label className="mb-2 block text-sm text-[#D8B65A]">
              Mahkeme / Kurum
            </label>
            <input
              value={form.authority}
              onChange={(e) => updateField("authority", e.target.value)}
              placeholder="Örn: Sulh Hukuk Mahkemesi"
              className={fieldClass}
            />
          </div>

          <div>
            <label className="mb-2 block text-sm text-[#D8B65A]">
              Başvuran / Davacı
            </label>
            <input
              value={form.applicant}
              onChange={(e) => updateField("applicant", e.target.value)}
              placeholder="Örn: Ahmet Yılmaz"
              className={fieldClass}
            />
          </div>

          <div>
            <label className="mb-2 block text-sm text-[#D8B65A]">
              Karşı Taraf / Davalı
            </label>
            <input
              value={form.opponent}
              onChange={(e) => updateField("opponent", e.target.value)}
              placeholder="Örn: Mehmet Kaya"
              className={fieldClass}
            />
          </div>

          <div>
            <label className="mb-2 block text-sm text-[#D8B65A]">
              Olay Özeti
            </label>
            <textarea
              value={form.event_summary}
              onChange={(e) => updateField("event_summary", e.target.value)}
              placeholder="Olayı kısa ama somut şekilde anlat."
              className={`${fieldClass} min-h-32 resize-y`}
            />
          </div>

          <div>
            <label className="mb-2 block text-sm text-[#D8B65A]">Talep</label>
            <textarea
              value={form.request_summary}
              onChange={(e) => updateField("request_summary", e.target.value)}
              placeholder="Mahkemeden/kurumdan ne talep ediliyor?"
              className={`${fieldClass} min-h-24 resize-y`}
            />
          </div>

          <div>
            <label className="mb-2 block text-sm text-[#D8B65A]">
              Ek Notlar
            </label>
            <textarea
              value={form.extra_notes}
              onChange={(e) => updateField("extra_notes", e.target.value)}
              placeholder="Adres, tarih, delil, özel not vb."
              className={`${fieldClass} min-h-24 resize-y`}
            />
          </div>

          <button
            type="submit"
            disabled={!canSubmit || isLoading}
            className="w-full rounded-full bg-gradient-to-r from-[#C9A227] to-[#D8B65A] px-8 py-3 font-semibold text-[#0B1220] shadow-lg shadow-[#C9A227]/12 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading ? "Dilekçe hazırlanıyor..." : "Dilekçe Taslağı Oluştur"}
          </button>

          {!canSubmit && (
            <p className="text-xs leading-5 text-[#94A3B8]">
              Devam etmek için en az olay özeti ve talep alanlarını doldur.
            </p>
          )}
        </form>
      </div>

      <div className="rounded-[32px] border border-[#C9A227]/8 bg-[#111827]/88 p-6 shadow-2xl shadow-black/40 backdrop-blur">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-[#D8B65A]">
              Dilekçe Taslağı
            </h2>
            <p className="mt-2 text-sm text-[#CBD5E1]">
              Oluşturulan metni kontrol edip kendi bilgilerine göre
              düzenleyebilirsin.
            </p>
          </div>

          {result?.petition_text && (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={copyPetition}
                className="rounded-full border border-[#C9A227]/12 px-4 py-2 text-sm text-[#F8FAFC] transition hover:bg-white/5"
              >
                {copied ? "Kopyalandı" : "Kopyala"}
              </button>

              <button
                type="button"
                onClick={exportAsPdf}
                className="rounded-full bg-gradient-to-r from-[#C9A227] to-[#D8B65A] px-4 py-2 text-sm font-semibold text-[#0B1220] shadow-lg shadow-[#C9A227]/10 transition hover:-translate-y-0.5"
              >
                PDF Olarak Kaydet
              </button>
            </div>
          )}
        </div>

        {result?.petition_text && (
          <div className="mb-4 rounded-2xl border border-[#C9A227]/10 bg-[#C9A227]/8 p-4 text-xs leading-6 text-[#D8B65A]">
            Bu metin yapay zekâ tarafından oluşturulmuş bir taslaktır. Hukuki
            danışmanlık niteliği taşımaz; kullanılmadan önce uzman kontrolünden
            geçirilmelidir.
          </div>
        )}

        <div className="min-h-[520px] rounded-3xl border border-[#C9A227]/8 bg-[#0B1220] p-5">
          {isLoading ? (
            <div className="inline-flex items-center gap-3 rounded-full border border-[#C9A227]/18 bg-[#C9A227]/8 px-4 py-2 text-sm text-[#D8B65A]">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#D8B65A]/20 border-t-[#C9A227]" />
              <span>Dilekçe metni oluşturuluyor...</span>
            </div>
          ) : result?.petition_text ? (
            <pre className="whitespace-pre-wrap font-sans text-sm leading-7 text-[#F8FAFC]">
              {result.petition_text}
            </pre>
          ) : (
            <p className="leading-8 text-[#94A3B8]">
              Bilgileri girip taslak oluşturduğunda dilekçe burada görünecek.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
