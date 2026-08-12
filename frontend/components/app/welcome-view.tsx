import { useState, useEffect, type ComponentProps } from 'react';
import { MicrophoneIcon, GradCapIcon } from '@phosphor-icons/react/dist/ssr';
import { Button } from '@/components/ui/button';

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  ref,
}: ComponentProps<'div'> & WelcomeViewProps) => {
  const [openCount, setOpenCount] = useState<number | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function fetchOpenCount() {
      try {
        let res = await fetch('/api/escalations');
        if (!res.ok) {
          res = await fetch('http://localhost:8765/api/escalations');
        }
        if (res.ok) {
          const data = await res.json();
          const items = data.requests || data.escalations || [];
          const count = items.filter(
            (r: any) => (r.status || 'OPEN').toUpperCase() === 'OPEN'
          ).length;
          if (isMounted) {
            setOpenCount(count);
          }
        }
      } catch (err) {
        // Fallback silently if server is not active
      }
    }

    fetchOpenCount();
    const interval = setInterval(fetchOpenCount, 8000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <div ref={ref} className="education-shell relative flex h-full min-h-0 w-full flex-col overflow-hidden text-white">
      <div className="hero-focus-circle hero-focus-circle-left" />
      <div className="hero-focus-circle hero-focus-circle-right" />
      <nav className="relative z-20 mx-auto flex w-full max-w-[1400px] flex-wrap items-center justify-between gap-3 rounded-[28px] border border-white/10 bg-slate-950/75 px-4 py-4 shadow-[0_24px_80px_rgba(10,18,58,.24)] backdrop-blur-xl sm:px-6 lg:px-8 flex-shrink-0">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-14 w-14 items-center justify-center rounded-3xl bg-white/10 p-1 shadow-[0_10px_30px_rgba(15,23,42,.18)] backdrop-blur-xl">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/shikshamitra-logo.png"
              alt="ShikshaMitra AI logo"
              className="max-h-full max-w-full object-contain"
            />
          </span>
          <div className="min-w-0">
            <p className="truncate text-base font-semibold text-white sm:text-lg">
              ShikshaMitra AI
            </p>
            <p className="hidden text-[10px] tracking-[.22em] text-cyan-200/70 uppercase sm:block">
              LEARN · UNDERSTAND · GROW
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-6 text-sm text-slate-300 md:flex">
            <a href="#home" className="transition hover:text-white">
              Home
            </a>
            <a href="#features" className="transition hover:text-white">
              Features
            </a>
            <a href="#subjects" className="transition hover:text-white">
              Subjects
            </a>
            <a href="#about" className="transition hover:text-white">
              About
            </a>
            <a
              href="/dashboard.html"
              target="_blank"
              rel="noopener noreferrer"
              title="View learner requests that need human/teacher support"
              className="inline-flex items-center gap-2 rounded-full border border-indigo-400/30 bg-indigo-950/70 px-3.5 py-1.5 text-xs font-semibold text-indigo-100 transition hover:border-indigo-400/60 hover:bg-indigo-900/90 hover:text-white"
            >
              <span>🎓 Teacher Help</span>
              {openCount !== null && (
                <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[11px] font-bold text-amber-300 border border-amber-500/30">
                  {openCount}
                </span>
              )}
            </a>
          </div>

          <details className="md:hidden">
            <summary className="flex cursor-pointer items-center gap-2 rounded-full border border-white/10 bg-slate-950/80 px-4 py-2 text-sm font-semibold text-slate-200 shadow-[0_10px_30px_rgba(15,23,42,.24)]">
              Menu
            </summary>
            <div className="mt-3 space-y-2 rounded-[24px] border border-white/10 bg-slate-950/95 p-4 shadow-[0_20px_60px_rgba(15,23,42,.28)]">
              <a
                href="#home"
                className="block rounded-2xl px-3 py-2 text-sm text-slate-200 transition hover:bg-white/5"
              >
                Home
              </a>
              <a
                href="#features"
                className="block rounded-2xl px-3 py-2 text-sm text-slate-200 transition hover:bg-white/5"
              >
                Features
              </a>
              <a
                href="#subjects"
                className="block rounded-2xl px-3 py-2 text-sm text-slate-200 transition hover:bg-white/5"
              >
                Subjects
              </a>
              <a
                href="#about"
                className="block rounded-2xl px-3 py-2 text-sm text-slate-200 transition hover:bg-white/5"
              >
                About
              </a>
              <a
                href="/dashboard.html"
                target="_blank"
                rel="noopener noreferrer"
                title="View learner requests that need human/teacher support"
                className="flex items-center justify-between rounded-2xl bg-indigo-950/60 px-3 py-2.5 text-sm font-medium text-indigo-200 transition hover:bg-indigo-900/80"
              >
                <span>🎓 Teacher Help Requests</span>
                {openCount !== null && (
                  <span className="rounded-full bg-amber-500/20 px-2.5 py-0.5 text-xs font-bold text-amber-300 border border-amber-500/30">
                    {openCount} Open
                  </span>
                )}
              </a>
            </div>
          </details>

          <div className="rounded-full border border-cyan-300/15 bg-slate-950/75 px-3 py-2 text-[10px] font-semibold tracking-[.16em] text-cyan-100 uppercase shadow-[0_0_30px_rgba(34,211,238,.12)] backdrop-blur-md md:flex">
            <span className="pulse-dot inline-block" />
            BUILT WITH MURF FALCON
          </div>
        </div>
      </nav>

      <main className="relative z-10 mx-auto flex h-full min-h-0 w-full max-w-[800px] flex-1 flex-col items-center justify-center px-4 py-6 text-center sm:px-6 sm:py-8 lg:px-8">
        <div className="flex flex-1 flex-col items-center justify-center text-center">
          <div className="hero-pill mb-4 inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/[.08] px-4 py-2 text-xs font-semibold tracking-[.2em] text-cyan-100 uppercase shadow-[0_16px_60px_rgba(34,211,238,.14)] backdrop-blur-md">
            <MicrophoneIcon weight="fill" className="h-4 w-4 text-cyan-300" />
            <span className="hidden items-center gap-2 sm:inline-flex">
              <span>VOICE AI TUTOR</span>
              <span className="waveform inline-flex items-center gap-1">
                <span className="wave" />
                <span className="wave" />
                <span className="wave" />
                <span className="wave" />
                <span className="wave" />
              </span>
            </span>
            <span className="sm:hidden">VOICE AI TUTOR</span>
          </div>

          <h1 className="max-w-2xl text-[clamp(2.75rem,5vw,4.75rem)] leading-[0.95] font-bold tracking-[-0.05em] text-white sm:text-[clamp(3rem,5vw,5rem)]">
            ShikshaMitra <span className="ai-gradient">AI</span>
          </h1>

          <p className="mt-4 text-lg font-medium text-indigo-100 sm:text-xl">
            Your Personal AI Learning Assistant
          </p>

          <p className="mt-4 max-w-xl text-sm leading-7 text-slate-300 sm:text-base">
            Learn <span className="text-cyan-200">Python</span>,{' '}
            <span className="text-violet-200">Spoken English</span>,{' '}
            <span className="text-indigo-200">Mathematics</span>,{' '}
            <span className="text-cyan-200">Science</span> and{' '}
            <span className="text-violet-200">Technology</span> through natural voice conversations.
          </p>

          <Button
            size="lg"
            onClick={onStartCall}
            className="group mt-8 flex w-full max-w-[320px] items-center justify-center gap-2 rounded-full bg-gradient-to-r from-violet-600 via-indigo-500 to-cyan-500 px-8 py-3 text-sm font-bold text-white shadow-[0_24px_90px_rgba(99,102,241,.24)] transition duration-200 hover:scale-[1.02] hover:brightness-110 focus-visible:ring-2 focus-visible:ring-cyan-200 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0b1028] active:scale-[0.98]"
          >
            <MicrophoneIcon
              weight="fill"
              className="h-5 w-5 transition-transform duration-200 group-hover:-rotate-6"
            />
            {startButtonText}
          </Button>

          <p className="mt-6 flex items-center justify-center gap-2 text-xs text-slate-400 sm:text-sm">
            <span className="inline-flex h-2.5 w-2.5 rounded-full bg-cyan-400" />
            Safe · Smart · Supportive
          </p>
        </div>
      </main>
    </div>
  );
};

