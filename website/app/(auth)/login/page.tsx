import { AuthForm } from "@/components/marketing/auth-form";

export default function LoginPage() {
  return (
    <AuthForm
      title="Sign in to KeyNetra"
      description="Access your authorization workspace, policy reviews, and developer tooling."
      submitLabel="Sign in"
    />
  );
}
