export default function Footer() {
  return (
    <footer className="border-t border-[#C9A227]/8 py-8">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-3 px-4 text-xs leading-6 text-[#94A3B8] md:px-8">
        <p>
          LexAI, hukuki karar arama, kısa değerlendirme ve dilekçe taslağı
          üretimi için geliştirilmiş yapay zekâ destekli bir demo/prototip
          uygulamasıdır.
        </p>

        <p>
          Sunulan içerikler hukuki danışmanlık, avukat görüşü veya kesin hukuki
          değerlendirme niteliği taşımaz. Doğruluk, güncellik ve somut olaya
          uygunluk bakımından uzman hukukçu kontrolü gerektirir.
        </p>

        <p className="text-[#D8B65A]">LexAI © 2026 — Demo amaçlıdır.</p>
      </div>
    </footer>
  );
}
