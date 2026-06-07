import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Briefcase, FileText, User, LogOut, Home } from 'lucide-react';
import './Layout.css';

const ApplicantLayout = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const navItems = [
    { path: '/applicant/dashboard', icon: Home, label: 'Dashboard' },
    { path: '/applicant/jobs', icon: Briefcase, label: 'Browse Jobs' },
    { path: '/applicant/applications', icon: FileText, label: 'My Applications' },
    { path: '/applicant/profile', icon: User, label: 'Profile' },
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

export default ApplicantLayout;

