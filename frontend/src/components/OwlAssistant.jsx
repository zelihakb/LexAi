import { useEffect, useMemo, useRef, useState } from "react";

export default function OwlAssistant({
  recentSearches,
  helpItems,
  exampleQueries,
}) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState("recent");
  const [side, setSide] = useState("right");
  const [yPos, setYPos] = useState(50);

  const [leftPupil, setLeftPupil] = useState({ x: 0, y: 0 });
  const [rightPupil, setRightPupil] = useState({ x: 0, y: 0 });

  const owlRef = useRef(null);
  const leftEyeRef = useRef(null);
  const rightEyeRef = useRef(null);

  const dragRef = useRef(false);
  const didDragRef = useRef(false);
  const dragOffsetRef = useRef(0);

  const recentList = useMemo(
    () => recentSearches?.slice(0, 5) ?? [],
    [recentSearches]
  );

  useEffect(() => {
    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

    const computePupilOffset = (eyeRef, clientX, clientY) => {
      if (!eyeRef.current) return { x: 0, y: 0 };

      const rect = eyeRef.current.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;

      const dx = clientX - centerX;
      const dy = clientY - centerY;

      return {
        x: clamp(dx / 18, -5, 5),
        y: clamp(dy / 18, -4, 4),
      };
    };

    const handleMouseMove = (e) => {
      setLeftPupil(computePupilOffset(leftEyeRef, e.clientX, e.clientY));
      setRightPupil(computePupilOffset(rightEyeRef, e.clientX, e.clientY));

      if (dragRef.current) {
        didDragRef.current = true;

        const vh = window.innerHeight;
        const nextTopPx = e.clientY - dragOffsetRef.current;
        const nextPercent = (nextTopPx / vh) * 100;

        setYPos(clamp(nextPercent, 14, 84));
        setSide(e.clientX < window.innerWidth / 2 ? "left" : "right");
      }
    };

    const handleMouseUp = () => {
      dragRef.current = false;
      document.body.style.userSelect = "";
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  const handleMouseDown = (e) => {
    if (!owlRef.current) return;

    dragRef.current = true;
    didDragRef.current = false;
    document.body.style.userSelect = "none";

    const rect = owlRef.current.getBoundingClientRect();
    dragOffsetRef.current = e.clientY - rect.top;
  };

  const handleClick = () => {
    if (didDragRef.current) {
      didDragRef.current = false;
      return;
    }
    setOpen((prev) => !prev);
  };

  const wrapperPositionClass =
    side === "right" ? "fixed right-4 z-50" : "fixed left-4 z-50";

  const panelPositionClass =
    side === "right"
      ? "mr-4 origin-right"
      : "ml-4 order-2 origin-left";

  const owlOrderClass = side === "right" ? "order-2" : "order-1";

  return (
    <>
      <style>{`
        @keyframes owlFloat {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-8px); }
        }

        @keyframes owlBlink {
          0%, 44%, 48%, 100% { transform: scaleY(1); }
          46% { transform: scaleY(0.08); }
        }

        .owl-float {
          animation: owlFloat 4.2s ease-in-out infinite;
        }

        .owl-eye-blink {
          animation: owlBlink 6s infinite;
          transform-origin: center;
        }

        .lexowl-scroll::-webkit-scrollbar {
          width: 8px;
        }

        .lexowl-scroll::-webkit-scrollbar-track {
          background: transparent;
        }

        .lexowl-scroll::-webkit-scrollbar-thumb {
          background: rgba(201, 162, 39, 0.22);
          border-radius: 999px;
        }
      `}</style>

      <div
        className={wrapperPositionClass}
        style={{ top: `${yPos}%`, transform: "translateY(-50%)" }}
      >
        <div className="flex items-center">
          {open && (
            <div
              className={`w-80 rounded-[28px] border border-white/8 bg-[#101827]/95 p-4 shadow-2xl shadow-black/50 backdrop-blur ${panelPositionClass}`}
            >
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-base font-semibold text-[#F8FAFC]">
                  LexOwl
                </h3>
                <button
                  onClick={() => setOpen(false)}
                  className="rounded-full px-2 py-1 text-sm text-[#94A3B8] transition hover:bg-white/5 hover:text-[#F8FAFC]"
                >
                  ✕
                </button>
              </div>

              <div className="mb-4 inline-flex rounded-full border border-white/8 bg-[#0B1220] p-1">
                <button
                  onClick={() => setTab("recent")}
                  className={`rounded-full px-3 py-2 text-xs font-medium transition ${
                    tab === "recent"
                      ? "bg-[#C9A227] text-[#0B1220]"
                      : "text-[#CBD5E1] hover:bg-white/5"
                  }`}
                >
                  Önceki Aramalar
                </button>
                <button
                  onClick={() => setTab("help")}
                  className={`rounded-full px-3 py-2 text-xs font-medium transition ${
                    tab === "help"
                      ? "bg-[#C9A227] text-[#0B1220]"
                      : "text-[#CBD5E1] hover:bg-white/5"
                  }`}
                >
                  Nasıl Kullanılır
                </button>
              </div>

              <div className="lexowl-scroll max-h-72 overflow-y-auto pr-1">
                {tab === "recent" ? (
                  <div className="space-y-2">
                    {recentList.length ? (
                      recentList.map((item, idx) => (
                        <div
                          key={`${item}-${idx}`}
                          className="rounded-2xl border border-white/6 bg-[#0B1220] px-3 py-3 text-sm leading-6 text-[#CBD5E1]"
                        >
                          {item}
                        </div>
                      ))
                    ) : (
                      <div className="rounded-2xl border border-dashed border-white/8 bg-[#0B1220] px-3 py-3 text-sm text-[#94A3B8]">
                        Henüz arama geçmişi yok.
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="space-y-2">
                    {helpItems.map((item, idx) => (
                      <div
                        key={idx}
                        className="rounded-2xl border border-white/6 bg-[#0B1220] px-3 py-3 text-sm leading-6 text-[#CBD5E1]"
                      >
                        {item}
                      </div>
                    ))}

                    <div className="mt-3">
                      <p className="mb-2 text-sm font-medium text-[#C9A227]">
                        Örnek Aramalar
                      </p>
                      <div className="space-y-2">
                        {exampleQueries.map((item, idx) => (
                          <div
                            key={idx}
                            className="rounded-2xl border border-white/6 bg-[#0B1220] px-3 py-3 text-sm leading-6 text-[#CBD5E1]"
                          >
                            {item}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          <button
            ref={owlRef}
            onMouseDown={handleMouseDown}
            onClick={handleClick}
            title="LexOwl yardım paneli"
            className={`relative ${owlOrderClass} ${
              open ? "" : "owl-float"
            } flex h-32 w-32 cursor-grab items-center justify-center rounded-full border border-[#C9A227]/12 bg-gradient-to-b from-[#35486B] via-[#233653] to-[#142033] shadow-2xl shadow-black/60 transition duration-300 hover:scale-105 active:cursor-grabbing`}
          >
            <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_50%_30%,rgba(255,255,255,0.16),transparent_58%)]" />
            <div className="absolute inset-1 rounded-full border border-white/6" />
            <div className="absolute inset-0 rounded-full shadow-[0_0_34px_rgba(201,162,39,0.08)]" />

            <div className="absolute -top-2 left-5 h-5 w-5 rotate-[-22deg] rounded-t-full border border-white/8 bg-[#2E4263]" />
            <div className="absolute -top-2 right-5 h-5 w-5 rotate-[22deg] rounded-t-full border border-white/8 bg-[#2E4263]" />

            <div className="absolute bottom-3 h-10 w-14 rounded-full bg-[#223653]/95 shadow-inner shadow-black/25" />

            <div className="relative z-10 flex items-center gap-3">
              <div
                ref={leftEyeRef}
                className="flex h-11 w-11 items-center justify-center rounded-full bg-[#F8FAFC] shadow-inner"
              >
                <div className="owl-eye-blink flex h-full w-full items-center justify-center rounded-full overflow-hidden">
                  <div
                    className="h-4 w-4 rounded-full bg-[#0B1220] transition-transform duration-75"
                    style={{
                      transform: `translate(${leftPupil.x}px, ${leftPupil.y}px)`,
                    }}
                  />
                </div>
              </div>

              <div
                ref={rightEyeRef}
                className="flex h-11 w-11 items-center justify-center rounded-full bg-[#F8FAFC] shadow-inner"
              >
                <div className="owl-eye-blink flex h-full w-full items-center justify-center rounded-full overflow-hidden">
                  <div
                    className="h-4 w-4 rounded-full bg-[#0B1220] transition-transform duration-75"
                    style={{
                      transform: `translate(${rightPupil.x}px, ${rightPupil.y}px)`,
                    }}
                  />
                </div>
              </div>
            </div>

            <div className="absolute top-[4.35rem] h-0 w-0 border-l-[9px] border-r-[9px] border-t-[13px] border-l-transparent border-r-transparent border-t-[#C9A227]" />
          </button>
        </div>
      </div>
    </>
  );
}
