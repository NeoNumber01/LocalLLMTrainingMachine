import React from 'react';
import { HashRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Runs from './pages/Runs';
import NewRun from './pages/NewRun';
import RunDetail from './pages/RunDetail';
import EvalDetail from './pages/EvalDetail';
import Models from './pages/Models';
import Datasets from './pages/Datasets';
import Adapters from './pages/Adapters';
import Compare from './pages/Compare';
import Reports from './pages/Reports';
import Settings from './pages/Settings';
import Playground from './pages/Playground';
import Evaluation from './pages/Evaluation';

const App: React.FC = () => {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/runs" element={<Runs />} />
          <Route path="/runs/:id" element={<RunDetail />} />
          <Route path="/runs/new" element={<NewRun />} />
          <Route path="/playground" element={<Playground />} />
          <Route path="/evaluation" element={<Evaluation />} />
          <Route path="/evaluation/:id" element={<EvalDetail />} />
          <Route path="/models" element={<Models />} />
          <Route path="/datasets" element={<Datasets />} />
          <Route path="/adapters" element={<Adapters />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </Layout>
    </Router>
  );
};

export default App;

