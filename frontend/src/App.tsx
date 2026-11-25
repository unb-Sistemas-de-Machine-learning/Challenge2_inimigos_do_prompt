import { useState } from 'react';
import { LandingPage } from './components/LandingPage';
import { MonitorView } from './components/MonitorView';

export function App() {
  const [view, setView] = useState<'landing' | 'monitor'>('landing');

  return view === 'landing' ? (
    <LandingPage onStartMonitoring={() => setView('monitor')} />
  ) : (
    <MonitorView onBack={() => setView('landing')} />
  );
}

export default App;
