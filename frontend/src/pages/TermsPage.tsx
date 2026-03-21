export function TermsPage() {
  return (
    <div className="prose prose-neutral max-w-3xl mx-auto py-12 px-4">
      <h1>Terms of Service</h1>
      <p className="text-muted-foreground">Effective: [Date]</p>

      <h2>1. Acceptance of Terms</h2>
      <p>
        By accessing or using Flywheel ("the Service"), you agree to be bound by
        these Terms of Service. If you do not agree, you may not use the Service.
      </p>

      <h2>2. Service Description</h2>
      <p>
        Flywheel is a knowledge compounding platform that helps teams build
        shared context through AI-powered skill execution, meeting preparation,
        and intelligence gathering. The Service processes your data using
        AI models to generate insights, reports, and recommendations.
      </p>

      <h2>3. User Accounts</h2>
      <p>
        You may access the Service anonymously with limited functionality or
        create an account via magic link authentication. You are responsible for
        maintaining the security of your account credentials and API keys. You
        must notify us immediately of any unauthorized access.
      </p>

      <h2>4. Acceptable Use</h2>
      <p>You agree not to:</p>
      <ul>
        <li>Use the Service for any illegal or unauthorized purpose</li>
        <li>Attempt to gain unauthorized access to the Service or its systems</li>
        <li>Interfere with or disrupt the Service or servers</li>
        <li>Upload malicious code or content</li>
        <li>Exceed reasonable usage limits or abuse API access</li>
        <li>Resell or redistribute the Service without authorization</li>
      </ul>

      <h2>5. Your Data</h2>
      <p>
        You retain ownership of all data you submit to the Service. By using the
        Service, you grant us a limited license to process your data solely for
        the purpose of providing the Service. We do not sell your data to third
        parties.
      </p>

      <h2>6. Bring Your Own Key (BYOK)</h2>
      <p>
        The Service supports a Bring Your Own Key model where you provide your
        own Anthropic API key. Your API key is encrypted at rest using
        AES-256-GCM. You are responsible for any charges incurred on your API
        key through the Service.
      </p>

      <h2>7. Third-Party Services</h2>
      <p>
        The Service integrates with third-party services including Supabase
        (authentication and data storage), Anthropic (AI processing), and Google
        Calendar (scheduling integration). Your use of these integrations is
        subject to the respective third-party terms of service.
      </p>

      <h2>8. Intellectual Property</h2>
      <p>
        The Service and its original content, features, and functionality are
        owned by Flywheel and are protected by international copyright,
        trademark, and other intellectual property laws.
      </p>

      <h2>9. Termination</h2>
      <p>
        We may terminate or suspend your account at any time for violation of
        these Terms. You may delete your account at any time through the Settings
        page. Upon account deletion, there is a 30-day grace period during which
        your data can be recovered, after which it is permanently deleted.
      </p>

      <h2>10. Limitation of Liability</h2>
      <p>
        The Service is provided "as is" without warranties of any kind. Flywheel
        shall not be liable for any indirect, incidental, special, consequential,
        or punitive damages resulting from your use of the Service. Our total
        liability shall not exceed the amount you paid for the Service in the
        twelve months preceding the claim.
      </p>

      <h2>11. Changes to Terms</h2>
      <p>
        We reserve the right to modify these Terms at any time. We will notify
        users of material changes via email or in-app notification. Continued use
        of the Service after changes constitutes acceptance of the modified Terms.
      </p>

      <h2>12. Governing Law</h2>
      <p>
        These Terms shall be governed by and construed in accordance with
        applicable laws, without regard to conflict of law provisions.
      </p>

      <h2>13. Contact</h2>
      <p>
        For questions about these Terms, contact us at{' '}
        <a href="mailto:legal@flywheel.app">legal@flywheel.app</a>.
      </p>
    </div>
  )
}
