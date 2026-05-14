export default function Navbar({
  onHomeClick,
  onPetitionClick,
  onDocumentClick,
}) {
  return (
    <header className="sticky top-0 z-40 border-b border-[#C9A227]/8 bg-[#0B1220]/92 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-4 py-4 md:px-8">
        <button
          type="button"
          onClick={onHomeClick}
          className="flex items-center gap-3 text-left"
        >
          <div className="rounded-full border border-[#C9A227]/18 bg-[#C9A227]/8 px-3 py-1 text-sm font-semibold text-[#D8B65A]">
            LexAI
          </div>
          <span className="hidden text-sm text-[#CBD5E1] md:inline">
            Hukuki Karar Asistanı
          </span>
        </button>

        <nav className="flex items-center gap-2 md:gap-3">
          <button
            type="button"
            onClick={onDocumentClick}
            className="rounded-full border border-[#C9A227]/12 px-4 py-2 text-sm text-[#F8FAFC] transition hover:bg-white/5"
          >
            Belge Oku
          </button>

          <button
            type="button"
            onClick={onPetitionClick}
            className="rounded-full border border-[#C9A227]/12 px-4 py-2 text-sm text-[#F8FAFC] transition hover:bg-white/5"
          >
            Dilekçe Yardımı
          </button>

          <button
            type="button"
            className="hidden rounded-full border border-[#C9A227]/12 px-4 py-2 text-sm text-[#F8FAFC] transition hover:bg-white/5 md:inline-flex"
          >
            Giriş Yap
          </button>

          <button
            type="button"
            className="hidden rounded-full bg-gradient-to-r from-[#C9A227] to-[#D8B65A] px-4 py-2 text-sm font-semibold text-[#0B1220] shadow-lg shadow-[#C9A227]/10 transition hover:-translate-y-0.5 md:inline-flex"
          >
            Kayıt Ol
          </button>
        </nav>
      </div>
    </header>
  );
}