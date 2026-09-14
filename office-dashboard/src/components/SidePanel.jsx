import TaskList from './TaskList';
import ActivityLog from './ActivityLog';

export default function SidePanel({ tasks, logs }) {
  return (
    <aside className="flex w-full flex-col border-l border-white/10 bg-black/40 backdrop-blur-xl lg:h-full lg:w-80 xl:w-96">
      <TaskList tasks={tasks} />
      <ActivityLog logs={logs} />
    </aside>
  );
}
