import { Radio } from 'lucide-react';

export default function ActivityLog({ logs }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col p-4 lg:overflow-hidden">
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
        <Radio className="h-4 w-4 animate-pulse-glow text-emerald-400" />
        アクティビティログ
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-1.5 pr-1 lg:overflow-y-auto">
        {logs.map((log) => (
          <div
            key={log.id}
            className="animate-log-in rounded-md border border-white/5 bg-white/[0.02] px-2.5 py-1.5 text-[11px] leading-snug text-slate-300"
          >
            <span className="mr-1.5 font-mono text-[10px] text-slate-500">{log.time}</span>
            {log.text}
          </div>
        ))}
      </div>
    </div>
  );
}
