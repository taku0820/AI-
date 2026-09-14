import { ListChecks, CheckCircle2, Clock, Loader2 } from 'lucide-react';

const STATUS_STYLE = {
  完了: { icon: CheckCircle2, cls: 'text-emerald-400' },
  進行中: { icon: Loader2, cls: 'text-cyan-400 animate-spin' },
  レビュー待ち: { icon: Clock, cls: 'text-amber-400' },
  未着手: { icon: Clock, cls: 'text-slate-500' },
};

export default function TaskList({ tasks }) {
  return (
    <div className="flex flex-col gap-2 border-b border-white/10 p-4">
      <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
        <ListChecks className="h-4 w-4 text-cyan-400" />
        実行中のタスク
      </div>
      <ul className="flex flex-col gap-2">
        {tasks.map((task) => {
          const style = STATUS_STYLE[task.status] || STATUS_STYLE['未着手'];
          const StatusIcon = style.icon;
          return (
            <li
              key={task.id}
              className="rounded-lg border border-white/10 bg-white/[0.03] p-2.5 transition hover:border-cyan-400/30"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-xs font-medium leading-snug text-slate-100">{task.title}</p>
                <StatusIcon className={`h-3.5 w-3.5 shrink-0 ${style.cls}`} />
              </div>
              <div className="mt-1.5 flex items-center gap-2">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-fuchsia-400 transition-all duration-500"
                    style={{ width: `${task.progress}%` }}
                  />
                </div>
                <span className="w-8 text-right font-mono text-[10px] text-slate-400">{task.progress}%</span>
              </div>
              <p className="mt-1 text-[10px] text-slate-500">{task.owner} ・ {task.status}</p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
