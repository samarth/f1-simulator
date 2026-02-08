interface Props {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const TABS = [
  { id: 'telemetry', label: 'Telemetry Analysis' },
  { id: 'strategy', label: 'Strategy Simulator' },
];

export default function TabNav({ activeTab, onTabChange }: Props) {
  return (
    <nav className="bg-surface-800 px-6 flex gap-0 border-b border-surface-400">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={`px-6 py-3 text-sm font-body font-semibold transition-colors relative ${
            activeTab === tab.id
              ? 'text-white'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          {tab.label}
          {activeTab === tab.id && (
            <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-f1-red" />
          )}
        </button>
      ))}
    </nav>
  );
}
