import { RefreshCw, TrendingUp, TrendingDown, Zap } from 'lucide-react';

export default function Header({ progress, onProgressChange, currentTask, onRefresh, spinning }) {
  const isUp = progress >= 50;
  const sign = progress >= 0 ? '+' : '';

  return (
    <header className="relative z-10 flex flex-col gap-4 border-b border-white/10 bg-black/40 px-4 py-4 backdrop-blur-xl sm:px-6 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-cyan-400/40 bg-cyan-500/10 shadow-[0_0_20px_-4px_rgba(34,211,238,0.6)]">
          <Zap className="h-6 w-6 text-cyan-300" />
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">現在のやる事</p>
          <p className="max-w-xs truncate text-sm font-medium text-slate-100 sm:max-w-md">{currentTask}</p>
        </div>
      </div>

      <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2">
        {isUp ? (
          <TrendingUp className="h-7 w-7 text-emerald-400" />
        ) : (
          <TrendingDown className="h-7 w-7 text-rose-400" />
        )}
        <span
          className={`font-mono text-4xl font-bold tracking-tight ${
            isUp ? 'text-emerald-400 drop-shadow-[0_0_12px_rgba(52,211,153,0.5)]' : 'text-rose-400 drop-shadow-[0_0_12px_rgba(251,113,133,0.5)]'
          }`}
        >
          {sign}
          {progress}%
        </span>
        <span className="hidden text-xs text-slate-400 sm:inline">進捗率</span>
      </div>

      <div className="flex flex-1 items-center gap-4 lg:max-w-md">
        <input
          type="range"
          min={0}
          max={100}
          value={progress}
          onChange={(e) => onProgressChange(Number(e.target.value))}
          className="h-2 w-full cursor-pointer appearance-none rounded-full bg-white/10 accent-cyan-400"
          style={{
            background: `linear-gradient(to right, #22d3ee ${progress}%, rgba(255,255,255,0.08) ${progress}%)`,
          }}
          aria-label="進捗率スライダー"
        />
        <span className="w-12 shrink-0 text-right font-mono text-sm text-cyan-300">{progress}%</span>
      </div>

      <button
        type="button"
        onClick={onRefresh}
        className="group flex items-center gap-2 rounded-xl border border-cyan-400/40 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-200 transition hover:bg-cyan-500/20 hover:shadow-[0_0_20px_-4px_rgba(34,211,238,0.7)] active:scale-95"
      >
        <RefreshCw className={`h-4 w-4 ${spinning ? 'animate-spin' : ''}`} />
        データ更新
      </button>
    </header>
  );
}
