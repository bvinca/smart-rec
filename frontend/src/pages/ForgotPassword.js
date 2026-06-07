import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Mail, Send } from 'lucide-react';
import { authApi } from '../api/auth';
import './Auth.css';

// request a reset link
// always 200 so we never reveal if the email exists
// DEBUG echoes reset URL when SMTP is off
const ForgotPassword = () => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [debugUrl, setDebugUrl] = useState(null);
  const [smtpDelivered, setSmtpDelivered] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const resp = await authApi.requestPasswordReset(email);
      setSubmitted(true);
      // hide DEBUG link if email actually sent
      const delivered = resp?.data?.smtp_delivered === true;
      setSmtpDelivered(delivered);
      if (!delivered && resp?.data?.debug_reset_url) {
        setDebugUrl(resp.data.debug_reset_url);
      }
      toast.success('If that email is registered, a reset link is on its way.');
    } catch (err) {
      // only real errors land here (network/server)
      toast.error('Could not start password reset. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <h1>Forgot your password?</h1>
          <p>
            Enter your account email and we’ll send you a single-use reset
            link that expires in 30 minutes.
          </p>
        </div>

        {!submitted ? (
          <form onSubmit={handleSubmit} className="auth-form">
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <div className="input-wrapper">
                <Mail size={20} />
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your.email@example.com"
                  required
                  className="input"
                />
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-full"
              disabled={loading}
            >
              {loading ? (
                <>
                  <div className="loading"></div>
                  Sending…
                </>
              ) : (
                <>
                  <Send size={20} />
                  Send reset link
                </>
              )}
            </button>
          </form>
        ) : (
          <div className="auth-form">
            <p>
              If an account exists for <strong>{email}</strong>, a password-reset
              link has been sent. Please check your inbox (and spam folder).
            </p>
            {smtpDelivered && (
              <p className="smtp-delivered-notice">
                ✓ Email delivered. Open the link from your inbox to continue.
              </p>
            )}
            {debugUrl && !smtpDelivered && (
              <div className="debug-token-notice">
                <p>
                  <strong>Dev mode fallback:</strong> the email could not be
                  delivered (SMTP disabled or send failed). Use this link to
                  continue the reset:
                </p>
                <p>
                  <Link to={debugUrl} className="auth-link">
                    {debugUrl}
                  </Link>
                </p>
              </div>
            )}
          </div>
        )}

        <div className="auth-footer">
          <p>
            Remembered it?{' '}
            <Link to="/login" className="auth-link">
              Back to sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
