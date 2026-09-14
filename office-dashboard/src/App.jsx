import { useEffect, useState } from 'react';
import Header from './components/Header';
import OfficeFloor from './components/OfficeFloor';
import SidePanel from './components/SidePanel';
import { useOfficeSimulation } from './hooks/useOfficeSimulation';
import { CURRENT_TASKS } from './data/officeData';

export default function App() {
  const [progress, setProgress] = useState(65);
  const [taskIndex, setTaskIndex] = useState(0);
  const [spinning, setSpinning] = useState(false);
  const { people, logs, tasks, refreshData } = useOfficeSimulation(progress);

  useEffect(() => {
    const id = setInterval(() => {
      setTaskIndex((i) => (i + 1) % CURRENT_TASKS.length);
    }, 9000);
    return () => clearInterval(id);
  }, []);

  const handleRefresh = () => {
    setSpinning(true);
    refreshData();
    setTaskIndex((i) => (i + 1) % CURRENT_TASKS.length);
    setTimeout(() => setSpinning(false), 700);
  };

  return (
    <div className="flex h-screen w-screen flex-col overflow-y-auto bg-[#05070d] text-slate-100 lg:overflow-hidden">
      <Header
        progress={progress}
        onProgressChange={setProgress}
        currentTask={CURRENT_TASKS[taskIndex]}
        onRefresh={handleRefresh}
        spinning={spinning}
      />
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <main className="min-h-[420px] flex-1 lg:min-h-0">
          <OfficeFloor people={people} />
        </main>
        <SidePanel tasks={tasks} logs={logs} />
      </div>
    </div>
  );
}
