import { useCallback, useEffect, useRef, useState } from 'react';
import { ROOMS, PEOPLE_SEED, TASK_SEED } from '../data/officeData';

const roomMap = Object.fromEntries(ROOMS.map((r) => [r.id, r]));

const OTHER_ROOMS = {
  dev: ['meeting', 'break', 'design'],
  design: ['meeting', 'break', 'dev'],
};

function nowStr() {
  return new Date().toLocaleTimeString('ja-JP', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function spotPercent(roomId, deskIndex) {
  const room = roomMap[roomId];
  const spot = room.desks[deskIndex % room.desks.length];
  return {
    x: room.x + (spot.x / 100) * room.w,
    y: room.y + (spot.y / 100) * room.h,
  };
}

function randomSpotInRoom(roomId, excludeIndex) {
  const room = roomMap[roomId];
  let idx = Math.floor(Math.random() * room.desks.length);
  if (room.desks.length > 1 && idx === excludeIndex) {
    idx = (idx + 1) % room.desks.length;
  }
  return { ...spotPercent(roomId, idx), deskIndex: idx };
}

function initialPeople() {
  return PEOPLE_SEED.map((p) => {
    const pos = spotPercent(p.home.room, p.home.desk);
    return {
      ...p,
      x: pos.x,
      y: pos.y,
      status: 'working',
      currentRoom: p.home.room,
      duration: 1.8,
    };
  });
}

export function useOfficeSimulation(progress) {
  const [people, setPeople] = useState(initialPeople);
  const [logs, setLogs] = useState(() => [
    { id: 0, time: nowStr(), text: 'オフィスシミュレーションを開始しました。' },
  ]);
  const [tasks, setTasks] = useState(TASK_SEED);

  const peopleRef = useRef(people);
  const progressRef = useRef(progress);
  const timersRef = useRef([]);

  useEffect(() => {
    peopleRef.current = people;
  }, [people]);

  useEffect(() => {
    progressRef.current = progress;
  }, [progress]);

  const pushLog = useCallback((text) => {
    setLogs((prev) => {
      const entry = { id: `${Date.now()}-${Math.random()}`, time: nowStr(), text };
      return [entry, ...prev].slice(0, 40);
    });
  }, []);

  const movePerson = useCallback(
    (personId) => {
      const person = peopleRef.current.find((p) => p.id === personId);
      if (!person || person.status === 'walking') return;

      const progressVal = progressRef.current;

      // 進捗率が低いときは、一部の人が座ったまま動かなくなる
      if (progressVal < 25 && Math.random() < 0.55) {
        setPeople((prev) =>
          prev.map((p) =>
            p.id === personId ? { ...p, status: p.status === 'idle' ? 'working' : 'idle' } : p,
          ),
        );
        return;
      }

      const candidates =
        person.currentRoom === 'meeting' || person.currentRoom === 'break'
          ? [person.home.room]
          : OTHER_ROOMS[person.home.room] || ['meeting', 'break'];
      const destRoomId = candidates[Math.floor(Math.random() * candidates.length)];
      const spot =
        destRoomId === person.home.room
          ? spotPercent(person.home.room, person.home.desk)
          : randomSpotInRoom(destRoomId);

      const speedFactor = 0.4 + (progressVal / 100) * 1.6;
      const duration = Math.max(0.6, 2.4 / speedFactor);
      const roomName = roomMap[destRoomId].name;

      setPeople((prev) =>
        prev.map((p) =>
          p.id === personId
            ? { ...p, status: 'walking', currentRoom: destRoomId, x: spot.x, y: spot.y, duration }
            : p,
        ),
      );

      pushLog(`${person.name}が${roomName}に移動しました`);

      const timer = setTimeout(() => {
        setPeople((cur) =>
          cur.map((p) =>
            p.id === personId
              ? {
                  ...p,
                  status: destRoomId === 'meeting' ? 'meeting' : destRoomId === 'break' ? 'break' : 'working',
                }
              : p,
          ),
        );
      }, duration * 1000);
      timersRef.current.push(timer);
    },
    [pushLog],
  );

  useEffect(() => {
    const speedFactor = 0.4 + (progress / 100) * 1.6;
    const interval = Math.max(500, 2600 / speedFactor);
    const activeCount = Math.max(1, Math.round(1 + progress / 35));

    const tick = () => {
      const idle = peopleRef.current.filter((p) => p.status !== 'walking');
      const shuffled = [...idle].sort(() => Math.random() - 0.5);
      shuffled.slice(0, activeCount).forEach((p) => movePerson(p.id));
    };

    const id = setInterval(tick, interval);
    return () => clearInterval(id);
  }, [progress, movePerson]);

  useEffect(() => {
    const timers = timersRef.current;
    return () => timers.forEach(clearTimeout);
  }, []);

  const refreshData = useCallback(() => {
    pushLog('データを更新しました');
    setTasks((prev) =>
      prev.map((t) => ({
        ...t,
        progress: Math.min(100, Math.max(0, t.progress + Math.floor(Math.random() * 15 - 5))),
        status: t.progress >= 96 ? '完了' : t.status,
      })),
    );
  }, [pushLog]);

  return { people, logs, tasks, refreshData };
}
