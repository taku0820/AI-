import { User } from 'lucide-react';

const STATUS_RING = {
  working: 'ring-cyan-400/70 shadow-[0_0_10px_2px_rgba(34,211,238,0.6)]',
  walking: 'ring-yellow-300/80 shadow-[0_0_14px_3px_rgba(253,224,71,0.7)]',
  meeting: 'ring-amber-400/70 shadow-[0_0_10px_2px_rgba(251,191,36,0.6)]',
  break: 'ring-emerald-400/70 shadow-[0_0_10px_2px_rgba(52,211,153,0.6)]',
  idle: 'ring-slate-500/50',
};

export default function PersonDot({ person }) {
  const ring = STATUS_RING[person.status] || STATUS_RING.working;
  const isMoving = person.status === 'walking';
  const isIdle = person.status === 'idle';

  return (
    <div
      className="group absolute -translate-x-1/2 -translate-y-1/2"
      style={{
        left: `${person.x}%`,
        top: `${person.y}%`,
        transition: `left ${person.duration}s ease-in-out, top ${person.duration}s ease-in-out`,
        zIndex: Math.round(person.y) + 10,
      }}
      title={`${person.name}（${person.dept}）`}
    >
      <div
        className={`relative flex h-4 w-4 items-center justify-center rounded-full ring-2 ${ring} ${
          isMoving ? 'animate-float-y' : ''
        }`}
        style={{ backgroundColor: person.color, opacity: isIdle ? 0.45 : 1 }}
      >
        <User className="h-2.5 w-2.5 text-black/70" strokeWidth={3} />
        {!isIdle && (
          <span
            className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-30"
            style={{ backgroundColor: person.color, animationDuration: isMoving ? '0.8s' : '2.4s' }}
          />
        )}
      </div>
      <span className="pointer-events-none absolute left-1/2 top-5 -translate-x-1/2 whitespace-nowrap rounded bg-black/70 px-1.5 py-0.5 text-[9px] font-medium text-slate-200 opacity-0 ring-1 ring-white/10 transition-opacity group-hover:opacity-100">
        {person.name}
      </span>
    </div>
  );
}
