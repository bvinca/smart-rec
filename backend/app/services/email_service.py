# email service - generates and (optionally) delivers candidate-facing emails.
# bridges the AI email generator and the EmailLog table.
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from ai.llm.email_generator import EmailGenerator
from app.models import Applicant, Job, EmailLog, Application
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys
import os

import logging
logger = logging.getLogger(__name__)

# put backend on the import path
backend_path = os.path.join(os.path.dirname(__file__), '..')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    from app.config import settings
except ImportError:
    class Settings:
        SMTP_ENABLED = False
        SMTP_HOST = "smtp.gmail.com"
        SMTP_PORT = 587
        SMTP_USER = ""
        SMTP_PASSWORD = ""
        SMTP_FROM_EMAIL = ""
        SMTP_FROM_NAME = "SmartRecruiter"
        SMTP_USE_TLS = True
    settings = Settings()


class EmailService:
    # generate + manage recruiter→candidate emails

    def __init__(self):
        self.generator = EmailGenerator()
    
    def generate_email_for_applicant(
        self,
        applicant_id: int,
        message_type: str,
        db: Session,
        tone: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        # build an email for one applicant. message_type ∈
        # {acknowledgment, feedback, rejection, interview_invitation}.
        # returns the content + metadata, logged as un-sent in EmailLog.
        applicant = db.query(Applicant).filter(Applicant.id == applicant_id).first()
        if not applicant:
            raise ValueError(f"Applicant with ID {applicant_id} not found")

        job = db.query(Job).filter(Job.id == applicant.job_id).first()
        if not job:
            raise ValueError(f"Job with ID {applicant.job_id} not found")

        candidate_name = f"{applicant.first_name} {applicant.last_name}"

        # roll up the score data
        score_data = {
            "overall_score": applicant.overall_score or 0.0,
            "skill_score": applicant.skill_score or 0.0,
            "experience_score": applicant.experience_score or 0.0,
            "education_score": applicant.education_score or 0.0
        }
        
        # build the email body
        email_content = self.generator.generate_email(
            candidate_name=candidate_name,
            job_title=job.title,
            message_type=message_type,
            score_data=score_data,
            additional_context=additional_context,
            tone=tone
        )

        # log it (not sent yet - just generated)
        email_log = EmailLog(
            applicant_id=applicant_id,
            job_id=applicant.job_id,
            recipient_email=applicant.email,
            message_type=message_type,
            email_content=email_content,
            sent=False  # not sent yet, just generated
        )
        db.add(email_log)
        db.commit()
        db.refresh(email_log)
        
        return {
            "email_id": email_log.id,
            "content": email_content,
            "recipient_email": applicant.email,
            "candidate_name": candidate_name,
            "job_title": job.title,
            "message_type": message_type,
            "generated_at": email_log.created_at.isoformat()
        }
    
    def generate_email_for_application(
        self,
        application_id: int,
        message_type: str,
        db: Session,
        tone: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        # same as above but keyed off an Application row (the user-based path
        # - applications submitted without a parsed Applicant)
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application:
            raise ValueError(f"Application with ID {application_id} not found")
        
        job = db.query(Job).filter(Job.id == application.job_id).first()
        if not job:
            raise ValueError(f"Job with ID {application.job_id} not found")
        
        # grab the candidate's name and email from either the user or applicant row
        candidate_name = "Candidate"
        recipient_email = None

        if application.applicant_id:
            # we have parsed applicant data
            applicant = db.query(Applicant).filter(Applicant.id == application.applicant_id).first()
            if applicant:
                candidate_name = f"{applicant.first_name} {applicant.last_name}"
                recipient_email = applicant.email

                # roll up the score data from the applicant
                score_data = {
                    "overall_score": applicant.overall_score or 0.0,
                    "skill_score": applicant.skill_score or 0.0,
                    "experience_score": applicant.experience_score or 0.0,
                    "education_score": applicant.education_score or 0.0
                }
            else:
                score_data = {}
        else:
            # no applicant row - fall back to user info
            from app.models import User
            user = db.query(User).filter(User.id == application.user_id).first()
            if user:
                candidate_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
                recipient_email = user.email
            score_data = {}
        
        if not recipient_email:
            raise ValueError(f"No email address found for application {application_id}")
        
        # build the email body
        email_content = self.generator.generate_email(
            candidate_name=candidate_name,
            job_title=job.title,
            message_type=message_type,
            score_data=score_data if score_data else None,
            additional_context=additional_context,
            tone=tone
        )

        # log it
        email_log = EmailLog(
            applicant_id=application.applicant_id,
            job_id=application.job_id,
            recipient_email=recipient_email,
            message_type=message_type,
            email_content=email_content,
            sent=False
        )
        db.add(email_log)
        db.commit()
        db.refresh(email_log)
        
        return {
            "email_id": email_log.id,
            "content": email_content,
            "recipient_email": recipient_email,
            "candidate_name": candidate_name,
            "job_title": job.title,
            "message_type": message_type,
            "generated_at": email_log.created_at.isoformat()
        }
    
    def send_email(
        self,
        email_id: int,
        db: Session,
        subject: Optional[str] = None
    ) -> Dict[str, Any]:
        # actually send a previously-generated email over SMTP
        email_log = db.query(EmailLog).filter(EmailLog.id == email_id).first()
        if not email_log:
            raise ValueError(f"Email with ID {email_id} not found")

        if email_log.sent:
            raise ValueError(f"Email with ID {email_id} has already been sent")

        # is SMTP turned on?
        if not settings.SMTP_ENABLED:
            raise ValueError("SMTP is not enabled. Please configure SMTP settings in your .env file")

        # make sure we have credentials
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            raise ValueError("SMTP credentials not configured. Please set SMTP_USER and SMTP_PASSWORD")

        # Gmail App Passwords arrive with spaces - strip them.
        smtp_password = settings.SMTP_PASSWORD.replace(" ", "")

        from_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
        from_name = settings.SMTP_FROM_NAME

        # pick a subject if the caller didn't give us one
        if not subject:
            message_type_titles = {
                "acknowledgment": "Thank You for Your Application",
                "feedback": "Application Feedback",
                "rejection": "Application Update",
                "interview_invitation": "Interview Invitation",
                "hired": "Job Offer - Congratulations!"
            }
            subject = message_type_titles.get(email_log.message_type, "Message from SmartRecruiter")
        
        # assemble the MIME message
        msg = MIMEMultipart()
        msg['From'] = f"{from_name} <{from_email}>"
        msg['To'] = email_log.recipient_email
        msg['Subject'] = subject

        # attach the body
        msg.attach(MIMEText(email_log.email_content, 'plain'))

        try:
            # pull timeout from settings (defaults to 10 seconds)
            timeout = getattr(settings, 'SMTP_TIMEOUT', 10)

            # connect to the SMTP server with the timeout
            if settings.SMTP_USE_TLS:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)

            # apply the timeout to every operation
            server.timeout = timeout

            # log in and send
            server.login(settings.SMTP_USER, smtp_password)
            server.send_message(msg)
            server.quit()

            # mark the email log as sent
            email_log.sent = True
            email_log.sent_at = datetime.now()
            db.commit()
            
            return {
                "success": True,
                "email_id": email_id,
                "recipient_email": email_log.recipient_email,
                "sent_at": email_log.sent_at.isoformat(),
                "message": "Email sent successfully"
            }
        except smtplib.SMTPAuthenticationError as e:
            error_code = str(e).split('(')[1].split(',')[0] if '(' in str(e) else None
            if error_code == '535' or 'BadCredentials' in str(e) or 'Username and Password not accepted' in str(e):
                error_msg = (
                    "Gmail authentication failed. Gmail requires an App Password instead of your regular password. "
                    "To fix this:\n"
                    "1. Go to https://myaccount.google.com/apppasswords\n"
                    "2. Sign in with your Google account\n"
                    "3. Select 'Mail' and 'Other (Custom name)'\n"
                    "4. Enter 'SmartRecruiter' as the name\n"
                    "5. Click 'Generate'\n"
                    "6. Copy the 16-character password (no spaces)\n"
                    "7. Use this App Password in your SMTP_PASSWORD setting\n\n"
                    f"Original error: {str(e)}"
                )
            else:
                error_msg = f"SMTP authentication failed: {str(e)}"
            logger.exception(f"EmailService: {error_msg}")
            raise ValueError(error_msg)
        except (TimeoutError, OSError) as e:
            error_msg = f"SMTP connection timeout or network error: {str(e)}. Please check your internet connection and try again."
            logger.exception(f"EmailService: {error_msg}")
            raise ValueError(error_msg)
        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {str(e)}"
            logger.exception(f"EmailService: {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.exception(f"EmailService: {error_msg}")
            raise ValueError(error_msg)
    
    def get_email_history(
        self,
        applicant_id: Optional[int] = None,
        job_id: Optional[int] = None,
        db: Session = None
    ) -> list:
        # email history filtered by applicant and/or job
        query = db.query(EmailLog)
        
        if applicant_id:
            query = query.filter(EmailLog.applicant_id == applicant_id)
        if job_id:
            query = query.filter(EmailLog.job_id == job_id)
        
        emails = query.order_by(EmailLog.created_at.desc()).all()
        
        return [
            {
                "id": email.id,
                "recipient_email": email.recipient_email,
                "message_type": email.message_type,
                "email_content": email.email_content,
                "sent": email.sent,
                "sent_at": email.sent_at.isoformat() if email.sent_at else None,
                "created_at": email.created_at.isoformat()
            }
            for email in emails
        ]


# transactional emails (password reset) - no EmailLog row

def send_transactional_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    timeout: int = 10,
) -> bool:
    # plain-text SMTP send. never raises - returns False on any failure
    # (SMTP disabled, missing creds, network, auth). callers handle the
    # fallback (e.g. the DEBUG echo on /request-password-reset).
    # failure paths log at warning level - fallback is intentional.
    if not getattr(settings, "SMTP_ENABLED", False):
        logger.info("Transactional email skipped: SMTP_ENABLED is False.")
        return False
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("Transactional email skipped: SMTP credentials missing.")
        return False

    # Gmail App Passwords come with spaces when generated from the UI - strip them.
    smtp_password = settings.SMTP_PASSWORD.replace(" ", "")
    from_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
    from_name = getattr(settings, "SMTP_FROM_NAME", "SmartRecruiter")

    msg = MIMEMultipart()
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    server = None
    try:
        if settings.SMTP_USE_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)
        server.login(settings.SMTP_USER, smtp_password)
        server.send_message(msg)
        logger.info("Transactional email sent to %s (subject=%r)", to_email, subject)
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.warning("Transactional email auth failed for %s: %s", to_email, e)
        return False
    except Exception as e:  # noqa: BLE001 - intentional broad catch
        logger.warning("Transactional email send failed for %s: %s", to_email, e)
        return False
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass


def send_password_reset_email(*, to_email: str, reset_url: str, frontend_base_url: Optional[str] = None) -> bool:
    # compose + send a password-reset email. `reset_url` is the path-relative
    # URL from auth router; we prepend the frontend base URL so the link is
    # clickable in mail clients. returns True/False - never raises.
    base = frontend_base_url or getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3000")
    full_url = reset_url if reset_url.startswith("http") else f"{base.rstrip('/')}{reset_url}"

    subject = "SmartRecruiter — Password reset"
    body = (
        "Hello,\n\n"
        "We received a request to reset the password on your SmartRecruiter "
        "account. To choose a new password, follow this single-use link "
        "within the next 30 minutes:\n\n"
        f"  {full_url}\n\n"
        "If you did not request a reset, you can ignore this message — your "
        "password has not changed.\n\n"
        "SmartRecruiter\n"
    )
    return send_transactional_email(to_email=to_email, subject=subject, body=body)