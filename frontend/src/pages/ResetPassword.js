import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Lock, Check } from 'lucide-react';
import { authApi } from '../api/auth';
import './Auth.css';

// set new password with ?token=
// success revokes refresh tokens everywhere
const ResetPassword = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') || '';
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!token) {
      toast.error('No reset token in the URL. Please use the link from your email.');
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error('Passwords do not match.');
      return;
    }
    if (newPassword.length < 8) {
      toast.error('Password must be at least 8 characters.');
      return;
    }
    setLoading(true);
    try {
      await authApi.confirmPasswordReset(token, newPassword);
      toast.success('Password reset. Please sign in with the new password.');
      navigate('/login');
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Reset failed.';
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <h1>Choose a new password</h1>
          <p>
            This link is single-use and expires shortly. Pick a password of
            at least 8 characters.
          </p>
        </div>

        {!token && (
          <p className="error-text">
            Missing reset token. Please follow the link from your reset email.
          </p>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label htmlFor="newPassword">New password</label>
            <div className="input-wrapper">
              <Lock size={20} />
              <input
                id="newPassword"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="At least 8 characters"
                required
                minLength={8}
                className="input"
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">Confirm new password</label>
            <div className="input-wrapper">
              <Lock size={20} />
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Repeat the new password"
                required
                minLength={8}
                className="input"
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-full"
            disabled={loading || !token}
          >
            {loading ? (
              <>
                <div className="loading"></div>
                Resetting…
              </>
            ) : (
              <>
                <Check size={20} />
                Reset password
              </>
            )}
          </button>
        </form>

        <div className="auth-footer">
          <p>
            <Link to="/login" className="auth-link">
              Back to sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default ResetPassword;
