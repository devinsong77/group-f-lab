import { useState } from 'react';
import './App.css';
import ReportManager from './pages/ReportManager';
import KnowledgeBase from './pages/KnowledgeBase';
import ReportCompare from './pages/ReportCompare';

const TABS = [
  { key: 'reports', label: '研报管理', icon: '📋' },
  { key: 'kb', label: '知识库', icon: '📚' },
  { key: 'compare', label: '研报比对', icon: '⚖️' },
];

function App() {
  const [activeTab, setActiveTab] = useState('reports');

  return (
    <div>
      <nav className="app-nav">
        <div className="app-nav-inner">
          <div className="app-logo">
            <div className="app-logo-icon">投</div>
            投研分析平台
          </div>
          <div className="tab-nav">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                className={`tab-btn ${activeTab === tab.key ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </nav>
      <main className="app-content">
        {activeTab === 'reports' && <ReportManager />}
        {activeTab === 'kb' && <KnowledgeBase />}
        {activeTab === 'compare' && <ReportCompare />}
      </main>
    </div>
  );
}

export default App;
