import { type ComponentProps, useEffect, useState } from 'react';
import { MicrophoneIcon } from '@phosphor-icons/react/dist/ssr';
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
            (r: { status?: string }) => (r.status || 'OPEN').toUpperCase() === 'OPEN'
          ).length;
          if (isMounted) {
            setOpenCount(count);
          }
        }
      } catch {
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
    <div
      ref={ref}
      className="education-shell relative flex h-full min-h-0 w-full flex-col overflow-hidden text-white"
    >
      <div className="hero-focus-circle hero-focus-circle-left" />
      <div className="hero-focus-circle hero-focus-circle-right" />
      <nav className="relative z-20 mx-auto mt-4 flex w-full max-w-[1400px] flex-shrink-0 items-center justify-between gap-6 px-6 py-4 sm:mt-6 sm:px-8">
        {/* LEFT: Branding */}
        <div className="flex min-w-0 items-center gap-3.5">
          <span className="flex h-[50px] w-[50px] flex-shrink-0 items-center justify-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/shikshamitra-logo.png"
              alt="ShikshaMitra AI logo"
              className="max-h-full max-w-full object-contain"
            />
          </span>
          <div className="min-w-0">
            <p className="truncate text-base font-bold tracking-tight text-white sm:text-lg">
              ShikshaMitra AI
            </p>
            <p className="hidden text-[10px] font-semibold tracking-[.2em] text-cyan-300 uppercase sm:block">
              LEARN · UNDERSTAND · GROW
            </p>
          </div>
        </div>

        {/* RIGHT: Action Buttons & Tech Badge */}
        <div className="flex items-center gap-4 sm:gap-5">
          <div className="hidden items-center gap-4 md:flex">
            {/* Teacher Help Button */}
            <a
              href="/dashboard.html"
              target="_blank"
              rel="noopener noreferrer"
              title="View learner requests that need human/teacher support"
              className="inline-flex h-[36px] items-center justify-center gap-1.5 rounded-full border border-purple-500/30 bg-purple-500/5 px-3.5 py-2 text-[14px] font-medium text-purple-200 transition duration-200 hover:border-purple-400/50 hover:bg-purple-500/10 hover:text-purple-100"
            >
              <span>🎓 Teacher Help</span>
              {openCount !== null && (
                <span className="flex h-5 min-w-[20px] items-center justify-center rounded-full border border-purple-400/40 bg-purple-600/20 px-1 text-[11px] font-bold text-purple-300">
                  {openCount}
                </span>
              )}
            </a>

            {/* Call Analytics Button */}
            <a
              href="/call-analytics.html"
              target="_blank"
              rel="noopener noreferrer"
              title="View Day 8 call performance and exercise completion analytics"
              className="inline-flex h-[36px] items-center justify-center gap-1.5 rounded-full border border-cyan-400/20 bg-cyan-500/5 px-3.5 py-2 text-[14px] font-medium text-cyan-200 transition duration-200 hover:border-cyan-400/40 hover:bg-cyan-500/10 hover:text-cyan-100"
            >
              <span>📊 Call Analytics</span>
            </a>
          </div>

          {/* BUILT WITH MURF FALCON Tech Badge */}
          <div className="hidden h-[36px] items-center justify-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-500/5 px-3.5 text-[12px] font-bold tracking-[.15em] text-cyan-200 uppercase lg:flex">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.6)]" />
            <span>BUILT WITH MURF FALCON</span>
          </div>

          {/* Mobile Menu */}
          <details className="md:hidden">
            <summary className="flex cursor-pointer items-center gap-2 rounded-full border border-white/10 bg-slate-950/80 px-3.5 py-1.5 text-xs font-semibold text-slate-200 shadow-[0_10px_30px_rgba(15,23,42,.24)]">
              Menu
            </summary>
            <div className="mt-3 space-y-2 rounded-[24px] border border-white/10 bg-slate-950/95 p-3.5 shadow-[0_20px_60px_rgba(15,23,42,.28)]">
              <a
                href="/dashboard.html"
                target="_blank"
                rel="noopener noreferrer"
                title="View learner requests that need human/teacher support"
                className="flex items-center justify-between rounded-2xl border border-purple-500/30 bg-purple-950/50 px-3 py-2 text-[13px] font-semibold text-purple-100 transition hover:bg-purple-900/70"
              >
                <span>🎓 Teacher Help</span>
                {openCount !== null && (
                  <span className="rounded-full border border-amber-500/30 bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold text-amber-300">
                    {openCount}
                  </span>
                )}
              </a>
              <a
                href="/call-analytics.html"
                target="_blank"
                rel="noopener noreferrer"
                title="View Day 8 call performance and exercise completion analytics"
                className="flex items-center justify-between rounded-2xl border border-indigo-500/20 bg-slate-900/70 px-3 py-2 text-[13px] font-medium text-slate-200 transition hover:bg-slate-800/80"
              >
                <span>📊 Call Analytics</span>
              </a>
              <div className="flex items-center justify-center pt-1.5">
                <div className="inline-flex h-[32px] items-center gap-2 rounded-full border border-cyan-400/25 bg-cyan-950/40 px-3 text-[11px] font-bold tracking-[.2em] text-cyan-200/90 uppercase">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400" />
                  <span>BUILT WITH MURF FALCON</span>
                </div>
              </div>
            </div>
          </details>
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
