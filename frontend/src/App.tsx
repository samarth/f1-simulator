import { useState } from 'react';
import { SessionProvider } from './hooks/useSession';
import Header from './components/layout/Header';
import SessionSelector from './components/layout/SessionSelector';
import TabNav from './components/layout/TabNav';
import TelemetryView from './components/telemetry/TelemetryView';
import StrategyView from './components/strategy/StrategyView';

export default function App() {
  const [activeTab, setActiveTab] = useState('telemetry');

  return (
    <SessionProvider>
      <div className="min-h-screen bg-surface-900 text-white font-body">
        <Header />
        <SessionSelector />
        <TabNav activeTab={activeTab} onTabChange={setActiveTab} />
        <main className="p-6">
          {activeTab === 'telemetry' && <TelemetryView />}
          {activeTab === 'strategy' && <StrategyView />}
        </main>
      </div>
    </SessionProvider>
  );
}
