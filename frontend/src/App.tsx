import { SessionProvider } from './hooks/useSession';
import Header from './components/layout/Header';
import SessionSelector from './components/layout/SessionSelector';
import StrategyView from './components/strategy/StrategyView';

export default function App() {
  return (
    <SessionProvider>
      <div className="min-h-screen bg-surface-900 text-white font-body">
        <Header />
        <SessionSelector />
        <main className="p-6">
          <StrategyView />
        </main>
      </div>
    </SessionProvider>
  );
}
