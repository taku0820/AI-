import { Code2, Palette, Users, Coffee, Monitor, Leaf, Table2, Sofa } from 'lucide-react';
import { ROOMS, ROOM_THEME } from '../data/officeData';
import PersonDot from './PersonDot';

const ROOM_ICON = { Code2, Palette, Users, Coffee };

export default function OfficeFloor({ people }) {
  return (
    <div className="relative flex h-full w-full items-center justify-center overflow-hidden bg-[#070a14] p-4 sm:p-8">
      {/* 背景のグロー */}
      <div className="pointer-events-none absolute left-1/4 top-0 h-72 w-72 rounded-full bg-cyan-500/10 blur-[100px]" />
      <div className="pointer-events-none absolute bottom-0 right-1/4 h-72 w-72 rounded-full bg-fuchsia-500/10 blur-[100px]" />

      <div
        className="relative w-full max-w-4xl"
        style={{ perspective: '1800px', perspectiveOrigin: '50% 20%' }}
      >
        <div
          className="relative mx-auto aspect-[16/10] w-full rounded-2xl"
          style={{
            transform: 'rotateX(55deg) rotateZ(45deg) scale(0.82)',
            transformStyle: 'preserve-3d',
          }}
        >
          {/* フロアのベースパネル */}
          <div
            className="absolute inset-0 rounded-2xl border border-white/10 bg-[#0b1020]"
            style={{
              backgroundImage:
                'linear-gradient(rgba(56,189,248,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(56,189,248,0.08) 1px, transparent 1px)',
              backgroundSize: '5% 5%',
              boxShadow: '0 0 80px 10px rgba(34,211,238,0.08) inset, 0 40px 80px -20px rgba(0,0,0,0.8)',
            }}
          />

          {ROOMS.map((room) => {
            const theme = ROOM_THEME[room.color];
            const Icon = ROOM_ICON[room.icon];
            return (
              <div
                key={room.id}
                className={`absolute rounded-lg border ${theme.border} ${theme.bg} ${theme.glow}`}
                style={{
                  left: `${room.x}%`,
                  top: `${room.y}%`,
                  width: `${room.w}%`,
                  height: `${room.h}%`,
                }}
              >
                {/* ルームラベル */}
                <div className={`absolute left-2 top-1.5 flex items-center gap-1 rounded-md bg-black/50 px-1.5 py-0.5 text-[10px] font-semibold ${theme.text} backdrop-blur-sm`}>
                  <Icon className="h-3 w-3" />
                  {room.name}
                </div>

                {/* 会議室のテーブル */}
                {room.table && (
                  <div className="absolute left-1/2 top-1/2 flex h-[34%] w-[46%] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-md border border-amber-300/40 bg-amber-500/10">
                    <Table2 className="h-4 w-4 text-amber-300/70" />
                  </div>
                )}

                {/* 休憩スペースのカウンター */}
                {room.counter && (
                  <div className="absolute left-1/2 top-[8%] flex h-[14%] w-[60%] -translate-x-1/2 items-center justify-center gap-1 rounded-md border border-emerald-300/40 bg-emerald-500/10 text-emerald-200/80">
                    <Coffee className="h-3.5 w-3.5" />
                    <span className="text-[9px] font-medium">Cafe</span>
                  </div>
                )}

                {/* デスク・椅子 */}
                {room.desks.map((desk, i) => (
                  <div
                    key={i}
                    className="absolute flex h-4 w-4 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-sm border border-white/15 bg-white/5"
                    style={{ left: `${desk.x}%`, top: `${desk.y}%` }}
                  >
                    {room.id === 'break' ? (
                      <Sofa className="h-2.5 w-2.5 text-slate-400/70" />
                    ) : room.id === 'meeting' ? null : (
                      <Monitor className="h-2.5 w-2.5 text-slate-400/70" />
                    )}
                  </div>
                ))}

                {/* 観葉植物 */}
                {room.plants.map((plant, i) => (
                  <div
                    key={i}
                    className="absolute -translate-x-1/2 -translate-y-1/2 text-emerald-400/60"
                    style={{ left: `${plant.x}%`, top: `${plant.y}%` }}
                  >
                    <Leaf className="h-3.5 w-3.5" />
                  </div>
                ))}
              </div>
            );
          })}

          {/* スキャンライン演出 */}
          <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-2xl opacity-30">
            <div className="animate-scan h-1/3 w-full bg-gradient-to-b from-transparent via-cyan-400/20 to-transparent" />
          </div>

          {/* 人のドット */}
          {people.map((person) => (
            <PersonDot key={person.id} person={person} />
          ))}
        </div>
      </div>
    </div>
  );
}
