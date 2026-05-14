import { useEffect, useMemo, useRef, useState } from "react";
import { explainDocumentText, ocrDocumentImage } from "../services/api";

const documentTypes = [
  "Mahkeme / karar evrakı",
  "Dilekçe",
  "İcra / tebligat",
  "Diğer",
];

const fieldClass =
  "w-full rounded-2xl border border-[#C9A227]/8 bg-[#0B1220] px-4 py-3 text-sm text-[#F8FAFC] outline-none placeholder:text-[#94A3B8] focus:border-[#C9A227]/28";

export default function DocumentReader() {
  const [documentType, setDocumentType] = useState(documentTypes[0]);
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [ocrText, setOcrText] = useState("");
  const [ocrWarning, setOcrWarning] = useState("");
  const [explanation, setExplanation] = useState(null);
  const [isReading, setIsReading] = useState(false);
  const [isExplaining, setIsExplaining] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const previewUrlRef = useRef("");

  const canRead = Boolean(file) && !isReading;
  const canExplain = ocrText.trim().length >= 10 && !isExplaining;

  const fileLabel = useMemo(() => {
    if (!file) return "Henüz görsel seçilmedi.";
    const sizeMb = file.size / (1024 * 1024);
    return `${file.name} • ${sizeMb.toFixed(2)} MB`;
  }, [file]);

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
        previewUrlRef.current = "";
      }
    };
  }, []);

  const replacePreviewUrl = (nextUrl = "") => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
    }

    previewUrlRef.current = nextUrl;
    setPreviewUrl(nextUrl);
  };

  const handleFileChange = (event) => {
    const selectedFile = event.target.files?.[0] || null;

    setError("");
    setExplanation(null);
    setOcrWarning("");

    if (!selectedFile) {
      setFile(null);
      setOcrText("");
      replacePreviewUrl("");
      return;
    }

    const allowedTypes = ["image/png", "image/jpeg", "image/webp"];

    if (!allowedTypes.includes(selectedFile.type)) {
      setFile(null);
      setOcrText("");
      replacePreviewUrl("");
      setError("Sadece png, jpg, jpeg veya webp görsel yükleyebilirsin.");
      return;
    }

    const nextPreviewUrl = URL.createObjectURL(selectedFile);

    setFile(selectedFile);
    setOcrText("");
    replacePreviewUrl(nextPreviewUrl);
  };

  const handleReadText = async () => {
    if (!file || isReading) return;

    setIsReading(true);
    setError("");
    setExplanation(null);
    setOcrWarning("");

    try {
      const data = await ocrDocumentImage(file, documentType);
      setOcrText(data?.extracted_text || "");
      setOcrWarning(data?.warning || "");
    } catch (err) {
      setError(err.message || "Belge okunamadı.");
    } finally {
      setIsReading(false);
    }
  };

  const handleExplain = async () => {
    if (!canExplain) return;

    setIsExplaining(true);
    setError("");
    setExplanation(null);

    try {
      const data = await explainDocumentText(ocrText, documentType);
      setExplanation(data);
    } catch (err) {
      setError(err.message || "Belge açıklanamadı.");
    } finally {
      setIsExplaining(false);
    }
  };

  const handleCopy = async () => {
    if (!ocrText.trim()) return;

    try {
      await navigator.clipboard.writeText(ocrText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  };

  return (
    <section className="grid gap-6 lg:grid-cols-[420px_minmax(0,1fr)]">
      <div className="h-fit rounded-[32px] border border-[#C9A227]/8 bg-[#111827]/88 p-6 shadow-2xl shadow-black/40 backdrop-blur">
        <div className="mb-4 inline-flex rounded-full border border-[#C9A227]/18 bg-[#C9A227]/8 px-4 py-2 text-sm font-medium text-[#D8B65A]">
          Belge Oku
        </div>

        <h1 className="text-3xl font-bold leading-tight tracking-tight text-[#F8FAFC] md:text-4xl">
          Belge fotoğrafını yükle, metni çıkaralım.
        </h1>

        <p className="mt-3 text-sm leading-7 text-[#CBD5E1]">
          Mahkeme evrakı, dilekçe veya tebligat görselini yükleyebilirsin.
          Şimdilik yalnızca tek görsel desteklenir; PDF ve çok sayfalı belgeler
          bu MVP’de yok.
        </p>

        <div className="mt-5 rounded-3xl border border-amber-300/15 bg-amber-300/8 p-4 text-sm leading-6 text-amber-100">
          <strong className="text-[#D8B65A]">Kişisel veri uyarısı:</strong>{" "}
          Belgelerde T.C. kimlik numarası, adres, telefon, dosya numarası ve
          özel bilgiler bulunabilir. Paylaşmadan önce dikkatli ol.
        </div>

        <div className="mt-6 space-y-4">
          <div>
            <label className="mb-2 block text-sm text-[#D8B65A]">
              Belge Türü
            </label>
            <select
              value={documentType}
              onChange={(event) => setDocumentType(event.target.value)}
              className={fieldClass}
            >
              {documentTypes.map((type) => (
                <option key={type} value={type} className="bg-[#0B1220]">
                  {type}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-2 block text-sm text-[#D8B65A]">
              Görsel Yükle
            </label>

            <label className="flex cursor-pointer flex-col items-center justify-center rounded-3xl border border-dashed border-[#C9A227]/18 bg-[#0B1220] px-4 py-8 text-center transition hover:bg-white/5">
              <span className="text-sm font-semibold text-[#F8FAFC]">
                png / jpg / jpeg / webp
              </span>
              <span className="mt-2 text-xs leading-5 text-[#94A3B8]">
                Görsel net, düz ve iyi ışıkta olursa OCR daha iyi çalışır.
              </span>
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                onChange={handleFileChange}
                className="hidden"
              />
            </label>

            <p className="mt-2 text-xs text-[#94A3B8]">{fileLabel}</p>
          </div>

          {previewUrl && (
            <div className="overflow-hidden rounded-3xl border border-[#C9A227]/8 bg-[#0B1220]">
              <img
                src={previewUrl}
                alt="Yüklenen belge önizlemesi"
                className="max-h-72 w-full object-contain"
              />
            </div>
          )}

          <button
            type="button"
            onClick={handleReadText}
            disabled={!canRead}
            className="w-full rounded-full bg-gradient-to-r from-[#C9A227] to-[#D8B65A] px-8 py-3 font-semibold text-[#0B1220] shadow-lg shadow-[#C9A227]/12 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isReading ? "Metin okunuyor..." : "Metni Oku"}
          </button>

          {isReading && (
            <div className="inline-flex items-center gap-3 rounded-full border border-[#C9A227]/18 bg-[#C9A227]/8 px-4 py-2 text-sm text-[#D8B65A]">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#D8B65A]/20 border-t-[#C9A227]" />
              <span>Gemini Vision belgeyi okuyor...</span>
            </div>
          )}
        </div>
      </div>

      <div className="rounded-[32px] border border-[#C9A227]/8 bg-[#111827]/88 p-6 shadow-2xl shadow-black/40 backdrop-blur">
        <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-[#D8B65A]">OCR Metni</h2>
            <p className="mt-2 text-sm leading-6 text-[#CBD5E1]">
              Çıkan metni kontrol edip gerekirse düzenle. Sonra sade dille
              açıklatabilirsin.
            </p>
          </div>

          <button
            type="button"
            onClick={handleCopy}
            disabled={!ocrText.trim()}
            className="rounded-full border border-[#C9A227]/12 px-4 py-2 text-sm text-[#F8FAFC] transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {copied ? "Kopyalandı" : "Metni Kopyala"}
          </button>
        </div>

        {ocrWarning && (
          <div className="mb-4 rounded-2xl border border-amber-300/15 bg-amber-300/8 px-4 py-3 text-sm leading-6 text-amber-100">
            {ocrWarning}
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-2xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            {error}
          </div>
        )}

        <textarea
          value={ocrText}
          onChange={(event) => setOcrText(event.target.value)}
          placeholder="OCR sonucu burada görünecek. Metni elle düzeltebilirsin."
          className="min-h-[340px] w-full rounded-3xl border border-[#C9A227]/8 bg-[#0B1220] px-5 py-4 text-sm leading-7 text-[#F8FAFC] outline-none transition placeholder:text-[#94A3B8] focus:border-[#C9A227]/28"
        />

        <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <p className="text-xs leading-5 text-[#94A3B8]">
            Not: OCR hatalı olabilir. Tarih, süre, taraf, dosya numarası ve
            talepleri mutlaka kontrol et.
          </p>

          <button
            type="button"
            onClick={handleExplain}
            disabled={!canExplain}
            className="rounded-full bg-gradient-to-r from-[#C9A227] to-[#D8B65A] px-8 py-3 font-semibold text-[#0B1220] shadow-lg shadow-[#C9A227]/12 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isExplaining ? "Açıklanıyor..." : "Sade Dille Açıkla"}
          </button>
        </div>

        {isExplaining && (
          <div className="mt-6 inline-flex items-center gap-3 rounded-full border border-[#C9A227]/18 bg-[#C9A227]/8 px-4 py-2 text-sm text-[#D8B65A]">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#D8B65A]/20 border-t-[#C9A227]" />
            <span>Belge sadeleştiriliyor...</span>
          </div>
        )}

        {explanation && (
          <div className="mt-6 space-y-4 rounded-3xl border border-[#C9A227]/8 bg-[#0B1220] p-5">
            <div>
              <h3 className="text-lg font-semibold text-[#D8B65A]">
                Sade Açıklama
              </h3>
              <p className="mt-3 whitespace-pre-line leading-8 text-[#F8FAFC]">
                {explanation.plain_explanation}
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold text-[#D8B65A]">
                Önemli Noktalar
              </h3>
              <ul className="mt-3 space-y-2 text-sm leading-7 text-[#CBD5E1]">
                {(explanation.important_points || []).map((item, index) => (
                  <li key={`${item}-${index}`} className="flex gap-2">
                    <span className="text-[#D8B65A]">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="text-lg font-semibold text-[#D8B65A]">
                Olası Adımlar
              </h3>
              <ul className="mt-3 space-y-2 text-sm leading-7 text-[#CBD5E1]">
                {(explanation.possible_actions || []).map((item, index) => (
                  <li key={`${item}-${index}`} className="flex gap-2">
                    <span className="text-[#D8B65A]">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            {explanation.warning && (
              <div className="rounded-2xl border border-amber-300/15 bg-amber-300/8 px-4 py-3 text-sm leading-6 text-amber-100">
                {explanation.warning}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
