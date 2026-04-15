import { useState } from 'react';
import ReportManager from './pages/ReportManager';
import KnowledgeBase from './pages/KnowledgeBase';
import ReportCompare from './pages/ReportCompare';
import './App.css';

const TABS = [
  { key: 'reports', label: '研报管理' },
  { key: 'kb', label: '知识库' },
  { key: 'compare', label: '研报比对' },
];

function App() {
  const [activeTab, setActiveTab] = useState('reports');
  const [navigateTo, setNavigateTo] = useState(null);

  const handleNavigateToStock = (stockCode) => {
    setNavigateTo({ stockCode });
    setActiveTab('kb');
  };

  const renderPage = () => {
    switch (activeTab) {
      case 'reports':
        return <ReportManager onNavigateToStock={handleNavigateToStock} />;
      case 'kb':
        return (
          <KnowledgeBase
            initialStockCode={navigateTo?.stockCode}
            onNavigated={() => setNavigateTo(null)}
          />
        );
      case 'compare':
        return <ReportCompare />;
      default:
        return null;
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">投研分析平台</h1>
        <nav className="app-nav">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              className={`nav-tab ${activeTab === tab.key ? 'nav-tab-active' : ''}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>
      <main className="app-main">
        {renderPage()}
      </main>
    </div>
  );
}

export default App;
