import { Toaster } from "@/components/ui/toaster"
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClientInstance } from '@/lib/query-client'
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import PageNotFound from './lib/PageNotFound';
import { AuthProvider, useAuth } from '@/lib/AuthContext';
import UserNotRegisteredError from '@/components/UserNotRegisteredError';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import ScanHistory from './pages/ScanHistory';
import ScanDetail from './pages/ScanDetail';
import DatasetView from './pages/DatasetView';
import TwinView from './pages/TwinView';
import AdminPanel from './pages/AdminPanel';
import GroundTruthAdmin from './pages/GroundTruthAdmin';
import MapScanBuilder from './pages/MapScanBuilder';
import MapExport from './pages/MapExport';
import ReportViewer from './pages/ReportViewer';
import PortfolioView from './pages/PortfolioView';
import ClientWorkflow from './pages/ClientWorkflow';
import PilotDashboard from './pages/PilotDashboard';
import CommercialPackaging from './pages/CommercialPackaging';
import DeploymentPanel from './pages/DeploymentPanel';
import DeploymentSetupGuide from './pages/DeploymentSetupGuide';
import ProductionDashboard from './pages/ProductionDashboard';
import GoLiveChecklist from './pages/GoLiveChecklist';
import APITestConsole from './pages/APITestConsole';
// Add page imports here

const AuthenticatedApp = () => {
  const { isLoadingAuth, isLoadingPublicSettings, authError, navigateToLogin } = useAuth();

  // Show loading spinner while checking app public settings or auth
  if (isLoadingPublicSettings || isLoadingAuth) {
    return (
      <div className="fixed inset-0 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-slate-200 border-t-slate-800 rounded-full animate-spin"></div>
      </div>
    );
  }

  // Handle authentication errors
  if (authError) {
    if (authError.type === 'user_not_registered') {
      return <UserNotRegisteredError />;
    } else if (authError.type === 'auth_required') {
      // Redirect to login automatically
      navigateToLogin();
      return null;
    }
  }

  // Render the main app
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/history" element={<ScanHistory />} />
        <Route path="/history/:scanId" element={<ScanDetail />} />
        <Route path="/datasets/:scanId" element={<DatasetView />} />
        <Route path="/twin/:scanId" element={<TwinView />} />
        <Route path="/admin" element={<AdminPanel />} />
        <Route path="/ground-truth" element={<GroundTruthAdmin />} />
        <Route path="/map-builder" element={<MapScanBuilder />} />
        <Route path="/map-export/:scanId" element={<MapExport />} />
        <Route path="/map-export" element={<MapExport />} />
        <Route path="/reports/:scanId" element={<ReportViewer />} />
        <Route path="/reports" element={<ReportViewer />} />
        <Route path="/portfolio" element={<PortfolioView />} />
        <Route path="/workflow" element={<ClientWorkflow />} />
        <Route path="/pilots" element={<PilotDashboard />} />
        <Route path="/commercial" element={<CommercialPackaging />} />
        <Route path="/deploy" element={<DeploymentPanel />} />
        <Route path="/setup-guide" element={<DeploymentSetupGuide />} />
        <Route path="/ops" element={<ProductionDashboard />} />
        <Route path="/go-live" element={<GoLiveChecklist />} />
        <Route path="/api-console" element={<APITestConsole />} />
      </Route>
      <Route path="*" element={<PageNotFound />} />
    </Routes>
  );
};


function App() {

  return (
    <AuthProvider>
      <QueryClientProvider client={queryClientInstance}>
        <Router>
          <AuthenticatedApp />
        </Router>
        <Toaster />
      </QueryClientProvider>
    </AuthProvider>
  )
}

export default App