import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider, useIsFetching } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './context/AuthContext';
import { BlindModeProvider } from './context/BlindModeContext';
import ProtectedRoute from './components/ProtectedRoute';
import ApplicantLayout from './components/ApplicantLayout';
import RecruiterLayout from './components/RecruiterLayout';
import Login from './pages/Login';
import Register from './pages/Register';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import Jobs from './pages/Jobs';
import Applicants from './pages/Applicants';
import Analytics from './pages/Analytics';
import ApplicantDashboard from './pages/ApplicantDashboard';
import ApplicantProfile from './pages/ApplicantProfile';
import ApplicantApplications from './pages/ApplicantApplications';
import JobDetail from './pages/JobDetail';
import ApplicantJobs from './pages/ApplicantJobs';
import RecruiterDashboard from './pages/RecruiterDashboard';
import './App.css';

// overlay while any TanStack query is fetching
const GlobalLoadingIndicator = () => {
  const isFetching = useIsFetching();

  if (!isFetching) return null;

  return (
    <div className="global-loading-overlay">
      <div className="global-loading-spinner" />
      <p className="global-loading-message">Loading data from server…</p>
    </div>
  );
};

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

// send each role to its own dashboard
const RoleRedirect = () => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading"></div>
        <p>Loading...</p>
      </div>
    );
  }

  if (user?.role === 'recruiter') {
    return <Navigate to="/recruiter/dashboard" replace />;
  } else if (user?.role === 'applicant') {
    return <Navigate to="/applicant/dashboard" replace />;
  }

  return <Navigate to="/login" replace />;
};

function AppRoutes() {
  return (
    <Routes>
      {/* no auth */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      
      {/* home -> role dashboard */}
      <Route path="/" element={<RoleRedirect />} />

      {/* recruiter */}
      <Route
        path="/recruiter/dashboard"
        element={
          <ProtectedRoute requireRole="recruiter">
            <RecruiterLayout>
              <RecruiterDashboard />
            </RecruiterLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/recruiter/jobs"
        element={
          <ProtectedRoute requireRole="recruiter">
            <RecruiterLayout>
              <Jobs />
            </RecruiterLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/recruiter/jobs/:id/applicants"
        element={
          <ProtectedRoute requireRole="recruiter">
            <RecruiterLayout>
              <Applicants />
            </RecruiterLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/recruiter/applicants"
        element={
          <ProtectedRoute requireRole="recruiter">
            <RecruiterLayout>
              <Applicants />
            </RecruiterLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/recruiter/analytics"
        element={
          <ProtectedRoute requireRole="recruiter">
            <RecruiterLayout>
              <Analytics />
            </RecruiterLayout>
          </ProtectedRoute>
        }
      />

      {/* applicant */}
      <Route
        path="/applicant/dashboard"
        element={
          <ProtectedRoute requireRole="applicant">
            <ApplicantLayout>
              <ApplicantDashboard />
            </ApplicantLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/applicant/jobs"
        element={
          <ProtectedRoute requireRole="applicant">
            <ApplicantLayout>
              <ApplicantJobs />
            </ApplicantLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/applicant/jobs/:id"
        element={
          <ProtectedRoute requireRole="applicant">
            <ApplicantLayout>
              <JobDetail />
            </ApplicantLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/applicant/applications"
        element={
          <ProtectedRoute requireRole="applicant">
            <ApplicantLayout>
              <ApplicantApplications />
            </ApplicantLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/applicant/profile"
        element={
          <ProtectedRoute requireRole="applicant">
            <ApplicantLayout>
              <ApplicantProfile />
            </ApplicantLayout>
          </ProtectedRoute>
        }
      />

      {/* catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BlindModeProvider>
          <Router>
            <GlobalLoadingIndicator />
            <AppRoutes />
          </Router>
          <Toaster position="top-right" />
        </BlindModeProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
