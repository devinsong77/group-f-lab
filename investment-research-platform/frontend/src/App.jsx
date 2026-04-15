import { useState } from 'react';
import './App.css';
import ReportManager from './pages/ReportManager';
import KnowledgeBase from './pages/KnowledgeBase';
import ReportCompare from './pages/ReportCompare';

const TABS = [
  { key: 'reports', label: '研报管理' },
  { key: 'kb', label: '知识库' },
  { key: 'compare', label: '研报比对' },
];

function App() {
  const [activeTab, setActiveTab] = useState('reports');

  return (
    <div className="app">
      <header className="app-header">
        <h1>投研分析平台</h1>
        <nav className="tab-nav">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              className={`tab-btn ${activeTab === tab.key ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>
      <main>
        {activeTab === 'reports' && <ReportManager />}
        {activeTab === 'kb' && <KnowledgeBase />}
        {activeTab === 'compare' && <ReportCompare />}
      </main>
    </div>
  );
}

export default App;
