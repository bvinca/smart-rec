import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useBlindMode } from '../context/BlindModeContext';
import { Briefcase, Users, BarChart3, FileText, LogOut, Building2, Eye, EyeOff } from 'lucide-react';
import './Layout.css';

const RecruiterLayout = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { blindMode, toggleBlindMode } = useBlindMode();

  const navItems = [
    { path: '/recruiter/dashboard', icon: Briefcase, label: 'Jobs' },
    { path: '/recruiter/applicants', icon: Users, label: 'Applicants' },
    { path: '/recruiter/analytics', icon: BarChart3, label: 'Analytics' },
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="layout">
      <header className="header">
        <div className="header-content">
          <Link to="/" className="logo">
            <FileText size={28} />
            <span>SmartRecruiter</span>
          </Link>
          <nav className="nav">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`nav-item ${isActive ? 'active' : ''}`}
                >
                  <Icon size={20} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
          <div className="user-menu">
            <button
              className="btn-icon"
              onClick={toggleBlindMode}
              title={
                blindMode
                  ? 'Blind screening ON — candidate names hidden. Click to disable.'
                  : 'Blind screening OFF — click to hide candidate names, emails, and institutions.'
              }
              style={{
                color: blindMode ? '#2563eb' : undefined,
                background: blindMode ? '#dbeafe' : undefined,
                borderRadius: '6px',
                padding: '6px 10px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '12px',
              }}
            >
              {blindMode ? <EyeOff size={16} /> : <Eye size={16} />}
              <span style={{ marginLeft: '2px' }}>
                {blindMode ? 'Blind' : 'Identified'}
              </span>
            </button>
            {user?.company_name && (
              <span className="company-name">
                <Building2 size={16} />
                {user.company_name}
              </span>
            )}
            <span className="user-name">{user?.first_name || user?.email}</span>
            <button className="btn-icon" onClick={handleLogout} title="Logout">
              <LogOut size={20} />
            </button>
          </div>
        </div>
      </header>
      <main className="main-content">
        {children}
      </main>
    </div>
  );
};

export default RecruiterLayout;

