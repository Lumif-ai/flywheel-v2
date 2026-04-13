export function PrivacyPage() {
  return (
    <div className="prose prose-neutral max-w-3xl mx-auto py-12 px-4">
      <h1>Privacy Policy</h1>
      <p className="text-muted-foreground">Effective: [Date]</p>

      <h2>1. Information We Collect</h2>

      <h3>Account Data</h3>
      <p>
        When you create an account, we collect your email address for
        authentication purposes. If you use anonymous access, we generate a
        temporary identifier with no personal information.
      </p>

      <h3>Usage Data</h3>
      <p>
        We collect information about how you interact with the Service,
        including skill executions, chat interactions, and feature usage. This
        data is used to improve the Service and provide you with better
        recommendations.
      </p>

      <h3>Context Store Data</h3>
      <p>
        The core of the Service is your context store -- structured knowledge
        entries that accumulate over time. This includes company profiles,
        contact information, meeting notes, and intelligence gathered through
        skill execution. Your context store data is stored in Supabase-hosted
        PostgreSQL with row-level security. BYOK API keys are AES-256-GCM
        encrypted at rest.
      </p>

      <h3>Uploaded Files</h3>
      <p>
        You may upload documents (PDF, DOCX) for processing. These files are
        used solely for the purpose of extracting information for your context
        store and are not shared with other users.
      </p>

      <h2>2. How We Use Your Information</h2>
      <p>We use your information to:</p>
      <ul>
        <li>Provide and maintain the Service</li>
        <li>Process your data through AI models to generate insights</li>
        <li>Send transactional emails (magic links, team invitations)</li>
        <li>Improve the Service and develop new features</li>
        <li>Ensure security and prevent abuse</li>
      </ul>

      <h2>3. Third-Party Services</h2>
      <p>We use the following third-party services to operate Flywheel:</p>
      <ul>
        <li>
          <strong>Supabase</strong> -- Authentication, PostgreSQL database
          hosting, and file storage. Your data is stored in Supabase-managed
          infrastructure with encryption at rest.
        </li>
        <li>
          <strong>Anthropic API</strong> -- AI model processing for skill
          execution and chat. Your prompts and context data are sent to Anthropic
          for processing. Refer to{' '}
          <a
            href="https://www.anthropic.com/privacy"
            target="_blank"
            rel="noopener noreferrer"
          >
            Anthropic's Privacy Policy
          </a>{' '}
          for their data handling practices.
        </li>
        <li>
          <strong>Resend</strong> -- Transactional email delivery for magic
          links and team invitations. Only your email address and message
          content are shared with Resend.
        </li>
      </ul>

      <h2>4. Google Calendar Integration</h2>
      <p>
        When you connect your Google Calendar, Flywheel accesses the following
        data:
      </p>
      <ul>
        <li>
          <strong>Calendar events</strong> -- Event titles, times, attendees,
          descriptions, and meeting links for upcoming and recent events
        </li>
        <li>
          <strong>Calendar metadata</strong> -- Calendar names and IDs to
          identify which calendars to sync
        </li>
      </ul>
      <p>This data is used to:</p>
      <ul>
        <li>Display your upcoming meetings in the preparation view</li>
        <li>
          Generate meeting preparation briefs with attendee context from your
          context store
        </li>
        <li>Track meeting-related intelligence and follow-ups</li>
      </ul>
      <p>
        Google Calendar data is stored in your tenant's database with the same
        row-level security as all other data. We do not share your calendar data
        with other users or third parties. You can revoke Flywheel's access to
        your Google Calendar at any time through your{' '}
        <a
          href="https://myaccount.google.com/permissions"
          target="_blank"
          rel="noopener noreferrer"
        >
          Google Account permissions
        </a>{' '}
        page or through the Flywheel Settings page.
      </p>

      <h2>5. Data Storage and Security</h2>
      <p>
        Your data is stored in Supabase-hosted PostgreSQL databases with
        row-level security (RLS) ensuring tenant isolation. All data is
        encrypted in transit (TLS) and at rest. BYOK API keys are encrypted
        using AES-256-GCM before storage.
      </p>

      <h2>6. Data Retention</h2>
      <p>
        Your data is retained for as long as your account is active. When you
        delete your account, there is a 30-day grace period during which your
        data can be recovered. After the grace period, all your data including
        context entries, work items, skill runs, and uploaded files are
        permanently deleted.
      </p>

      <h2>7. Your Rights</h2>
      <p>You have the right to:</p>
      <ul>
        <li>
          <strong>Access</strong> -- View all your data through the Service
          interface
        </li>
        <li>
          <strong>Export</strong> -- Download all your data via the tenant export
          feature in Settings
        </li>
        <li>
          <strong>Deletion</strong> -- Delete your account and all associated
          data through Settings
        </li>
        <li>
          <strong>Correction</strong> -- Update your profile information at any
          time
        </li>
        <li>
          <strong>Revoke access</strong> -- Disconnect third-party integrations
          (e.g., Google Calendar) at any time
        </li>
      </ul>

      <h2>8. Cookies</h2>
      <p>
        The Service uses essential cookies and local storage for authentication
        tokens and session management. We do not use tracking cookies or
        third-party analytics cookies.
      </p>

      <h2>9. Children's Privacy</h2>
      <p>
        The Service is not intended for use by children under the age of 13. We
        do not knowingly collect personal information from children under 13.
      </p>

      <h2>10. Changes to This Policy</h2>
      <p>
        We may update this Privacy Policy from time to time. We will notify you
        of material changes via email or in-app notification. The updated policy
        will be effective upon posting.
      </p>

      <h2>11. Contact</h2>
      <p>
        For privacy-related questions or to exercise your rights, contact us at{' '}
        <a href="mailto:legal@lumif.ai">legal@lumif.ai</a>.
      </p>
    </div>
  )
}
