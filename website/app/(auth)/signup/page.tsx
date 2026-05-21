import { AuthForm } from "@/components/marketing/auth-form";

export default function SignupPage() {
  return (
    <AuthForm
      title="Create your KeyNetra account"
      description="Start evaluating authorization flows with a developer-first control plane."
      submitLabel="Create account"
    />
  );
}
