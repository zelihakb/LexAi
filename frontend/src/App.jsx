import { useEffect, useMemo, useState } from "react";
import Navbar from "./components/Navbar";
import ModeToggle from "./components/ModeToggle";
import SearchSection from "./components/SearchSection";
import FilterPanel from "./components/FilterPanel";
import ResultsSection from "./components/ResultsSection";
import PetitionSection from "./components/PetitionSection";
import OwlAssistant from "./components/OwlAssistant";
import Footer from "./components/Footer";
import { askQuestion, createPetition, findDecisions } from "./services/api";
import DocumentReader from "./components/DocumentReader";

import { exampleQueries, helpItems, loadingMessages } from "./data/mockData";

const askExamples = [
  "İdari para cezası kesinleşmeden ödeme emri düzenlenebilir mi?",
  "SSK’dan emeklilik şartlarını sağlayan kişinin Bağ-Kur borcu gerekçe gösterilerek aylığı engellenebilir mi?",
  "Kiracı farklı kira sözleşmesi ileri sürerse tahliye kararı verilebilir mi?",
];

const emptyPetitionForm = {
  petition_type: "",
  authority: "",
  applicant: "",
  opponent: "",
  event_summary: "",
  request_summary: "",
  extra_notes: "",
};

function normalizeFinalItems(data) {
  if (!data) return [];

  if (Array.isArray(data.final_items)) return data.final_items;
  if (Array.isArray(data.items)) return data.items;
  if (Array.isArray(data.results)) return data.results;
  if (Array.isArray(data.decisions)) return data.decisions;

  return [];
}

export default function App() {
  const [mode, setMode] = useState("ask");
  const [question, setQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [loadingIndex, setLoadingIndex] = useState(0);
  const [result, setResult] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState("");
  const [petitionForm, setPetitionForm] = useState(emptyPetitionForm);

  const [recentSearches, setRecentSearches] = useState(() => {
    try {
      const saved = localStorage.getItem("lexai_recent_searches");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [filters, setFilters] = useState({
    year: "",
    court: "",
    number: "",
  });

  useEffect(() => {
    try {
      localStorage.setItem(
        "lexai_recent_searches",
        JSON.stringify(recentSearches),
      );
    } catch {
      //
    }
  }, [recentSearches]);

  useEffect(() => {
    if (!isLoading) return;

    const interval = setInterval(() => {
      setLoadingIndex((prev) => (prev + 1) % loadingMessages.length);
    }, 1200);

    return () => clearInterval(interval);
  }, [isLoading]);

  const loadingText = useMemo(() => {
    if (mode === "petition") return "Dilekçe hazırlanıyor...";
    return loadingMessages[loadingIndex];
  }, [mode, loadingIndex]);

  const hasAnyFilter = useMemo(
    () => Object.values(filters).some((value) => String(value).trim() !== ""),
    [filters],
  );

  const canSearch = useMemo(() => {
    if (mode === "ask") return question.trim().length >= 5;
    if (mode === "find") return question.trim().length > 0 || hasAnyFilter;
    return false;
  }, [mode, question, hasAnyFilter]);

  const validationMessage = useMemo(() => {
    if (mode === "ask") {
      return question.trim().length >= 5
        ? "Hazır. Arama ve yorum üretme işlemini başlatabilirsin."
        : "En az 5 karakterlik bir hukuki soru yaz.";
    }

    if (mode === "find") {
      return canSearch
        ? "Hazır. Arama metni veya filtrelerle kararları bulabilirsin."
        : "Karar Bul modunda arama metni gir veya en az bir filtre doldur.";
    }

    return "";
  }, [mode, question, canSearch]);

  const addRecentSearch = (text) => {
    const clean = String(text || "").trim();
    if (!clean) return;

    setRecentSearches((prev) => {
      const next = [clean, ...prev.filter((item) => item !== clean)];
      return next.slice(0, 5);
    });
  };

  const buildRecentSearchLabel = () => {
    if (mode === "ask") return question.trim();

    if (mode === "petition") {
      return `Dilekçe: ${
        petitionForm.petition_type.trim() || petitionForm.request_summary.trim()
      }`;
    }

    const parts = [];
    if (question.trim()) parts.push(`Arama: ${question.trim()}`);
    if (filters.year.trim()) parts.push(`Yıl: ${filters.year.trim()}`);
    if (filters.court.trim()) parts.push(`Mahkeme: ${filters.court.trim()}`);
    if (filters.number.trim()) parts.push(`No: ${filters.number.trim()}`);

    return parts.join(" | ");
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!canSearch || isLoading) return;

    setIsLoading(true);
    setError("");
    setResult(null);
    setHasSearched(true);
    addRecentSearch(buildRecentSearchLabel());

    try {
      const data =
        mode === "ask"
          ? await askQuestion(question)
          : await findDecisions(question, filters);

      setResult(data);
    } catch (err) {
      setError(err.message || "Bir hata oluştu.");
    } finally {
      setIsLoading(false);
    }
  };

  const handlePetitionSubmit = async (e) => {
    e.preventDefault();
    if (isLoading) return;

    setIsLoading(true);
    setError("");
    setResult(null);
    setHasSearched(true);
    addRecentSearch(buildRecentSearchLabel());

    try {
      const data = await createPetition(petitionForm);
      setResult(data);
    } catch (err) {
      setError(err.message || "Dilekçe oluşturulamadı.");
    } finally {
      setIsLoading(false);
    }
  };

  const clearFilters = () => {
    setFilters({
      year: "",
      court: "",
      number: "",
    });
  };

  const filteredItems = useMemo(() => {
    return normalizeFinalItems(result).slice(0, 5);
  }, [result]);

  const summaryText = useMemo(() => {
    if (!hasSearched) return "";

    if (mode === "find") {
      return filteredItems.length
        ? `${filteredItems.length} karar bulundu.`
        : "Seçtiğin arama veya filtrelere uygun karar bulunamadı.";
    }

    return "";
  }, [hasSearched, mode, filteredItems]);

  const exampleChips = mode === "ask" ? askExamples : exampleQueries;

  const handleExampleClick = (value) => {
    setQuestion(value);
  };

  const handleModeChange = (nextMode) => {
    setMode(nextMode);
    setResult(null);
    setHasSearched(false);
    setError("");
    setQuestion("");
  };

  const goHome = () => {
    handleModeChange("ask");
  };

  return (
    <div className="min-h-screen overflow-x-hidden bg-[#0B1220] text-[#F8FAFC]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(201,162,39,0.045),transparent_25%),radial-gradient(circle_at_bottom_right,rgba(30,41,59,0.22),transparent_30%)]" />
      <div className="absolute inset-0 bg-[linear-gradient(rgba(201,162,39,0.012)_1px,transparent_1px),linear-gradient(90deg,rgba(201,162,39,0.012)_1px,transparent_1px)] bg-[size:42px_42px] opacity-30" />

      <div className="relative z-10">
        <Navbar onHomeClick={goHome} />

        <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 md:px-8">
          <div className="flex justify-center">
            <ModeToggle mode={mode} setMode={handleModeChange} />
          </div>

          {mode === "document" ? (
            <DocumentReader />
          ) : mode === "petition" ? (
            <>
              <PetitionSection
                form={petitionForm}
                setForm={setPetitionForm}
                handlePetitionSubmit={handlePetitionSubmit}
                isLoading={isLoading}
                result={result}
              />

              {error && (
                <div className="rounded-2xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                  {error}
                </div>
              )}
            </>
          ) : (
            <>
              <SearchSection
                question={question}
                setQuestion={setQuestion}
                handleSearch={handleSearch}
                isLoading={isLoading}
                loadingText={loadingText}
                mode={mode}
                canSearch={canSearch}
                validationMessage={validationMessage}
                exampleChips={exampleChips}
                onExampleClick={handleExampleClick}
              />

              {error && (
                <div className="rounded-2xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                  {error}
                </div>
              )}

              {mode === "find" ? (
                <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
                  <FilterPanel
                    filters={filters}
                    setFilters={setFilters}
                    mode={mode}
                    clearFilters={clearFilters}
                  />

                  <ResultsSection
                    mode={mode}
                    result={result}
                    filteredItems={filteredItems}
                    hasSearched={hasSearched}
                    summaryText={summaryText}
                  />
                </div>
              ) : (
                <ResultsSection
                  mode={mode}
                  result={result}
                  filteredItems={filteredItems}
                  hasSearched={hasSearched}
                  summaryText={summaryText}
                />
              )}
            </>
          )}

          <Footer />
        </main>

        <OwlAssistant
          recentSearches={recentSearches}
          helpItems={helpItems}
          exampleQueries={exampleQueries}
        />
      </div>
    </div>
  );
}
