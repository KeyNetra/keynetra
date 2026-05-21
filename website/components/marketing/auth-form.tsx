"use client";

import { Github, LoaderCircle, Mail } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function AuthForm({
  title,
  description,
  submitLabel
}: {
  title: string;
  description: string;
  submitLabel: string;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (!email || !password) {
      setError("Enter both email and password to continue.");
      return;
    }

    setLoading(true);
    await new Promise((resolve) => window.setTimeout(resolve, 900));
    setLoading(false);
    setError("Authentication is not connected yet. This is a production UI stub.");
  }

  return (
    <Card className="w-full max-w-md border-border/70 bg-background/85 p-8 shadow-2xl">
      <div className="space-y-3 text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">{title}</h1>
        <p className="text-sm leading-7 text-muted-foreground">{description}</p>
      </div>
      <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
        <Input
          type="email"
          placeholder="you@company.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <Input
          type="password"
          placeholder="Enter your password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        {error ? <p className="text-sm text-rose-400">{error}</p> : null}
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : null}
          {submitLabel}
        </Button>
      </form>
      <div className="my-6 flex items-center gap-3 text-xs uppercase tracking-[0.24em] text-muted-foreground">
        <div className="h-px flex-1 bg-border" />
        <span>or continue with</span>
        <div className="h-px flex-1 bg-border" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Button variant="secondary">
          <Mail className="mr-2 h-4 w-4" />
          Google
        </Button>
        <Button variant="secondary">
          <Github className="mr-2 h-4 w-4" />
          GitHub
        </Button>
      </div>
    </Card>
  );
}
