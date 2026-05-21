"use client";

import Link from "next/link";
import {
  ArrowRight,
  Blocks,
  Box,
  Cable,
  CheckCircle2,
  Cpu,
  FileCode2,
  FileSearch,
  Fingerprint,
  GitBranch,
  Layers3,
  LockKeyhole,
  Network,
  Orbit,
  Shield,
  Workflow
} from "lucide-react";
import {
  motion,
  type MotionValue,
  useMotionTemplate,
  useMotionValue,
  useScroll,
  useSpring,
  useTransform
} from "framer-motion";
import { useMemo, useRef, type ReactNode } from "react";

import { CodeTabs } from "@/components/marketing/code-tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Feature = {
  icon: typeof Shield;
  title: string;
  summary: string;
  details: string;
  signal: string;
};

const problems = [
  "Authorization logic is scattered across APIs, workers, gateways, and background jobs.",
  "RBAC becomes hard to maintain once product behavior depends on teams, resources, and exceptions.",
  "Hardcoded permission checks create security bugs when one service drifts from another.",
  "Microservices multiply complexity because every service reimplements part of the decision model.",
  "No central decision layer means no reliable audit trail for why access was granted or denied."
];

const features: Feature[] = [
  {
    icon: Shield,
    title: "Centralized Policy Engine",
    summary: "Define and manage permissions in one place.",
    details:
      "Move authorization logic out of application handlers and into a dedicated decision layer. Teams update policy centrally instead of pushing permission changes through every service.",
    signal: "policy graph"
  },
  {
    icon: Fingerprint,
    title: "Fine-grained Authorization",
    summary: "Control access at resource and action level.",
    details:
      "Evaluate decisions against specific resources, actions, and runtime context. This supports access models that depend on ownership, role, tenant, and business state.",
    signal: "resource match"
  },
  {
    icon: Layers3,
    title: "Multi-model Support",
    summary: "RBAC, ReBAC, and ACL in one system.",
    details:
      "Use roles for baseline access, relationships for collaboration, and ACLs for direct grants. KeyNetra combines these models without splitting logic across separate tools.",
    signal: "model merge"
  },
  {
    icon: Workflow,
    title: "Real-time Decision Engine",
    summary: "Millisecond authorization checks for live systems.",
    details:
      "Serve access checks on synchronous request paths without duplicating policy state inside every application. The engine is designed for APIs, background jobs, and internal tooling.",
    signal: "latency path"
  },
  {
    icon: FileSearch,
    title: "Audit Logs",
    summary: "Track every access decision.",
    details:
      "Capture who requested access, what was evaluated, and why the final decision was returned. That gives engineering and security teams a clearer operating picture.",
    signal: "decision trail"
  },
  {
    icon: FileCode2,
    title: "SDKs",
    summary: "Easy integration across services.",
    details:
      "Integrate from Node.js, Go, and Python using predictable request shapes and API-first contracts. Teams can adopt KeyNetra without inventing custom wrappers in each stack.",
    signal: "typed client"
  }
];

const architectureSteps = [
  {
    icon: Box,
    title: "App sends access request",
    description: "Your API, worker, or gateway sends user, action, resource, and context."
  },
  {
    icon: Cable,
    title: "SDK forwards to KeyNetra",
    description: "Language SDKs normalize the request and attach auth, tenant, and tracing metadata."
  },
  {
    icon: Cpu,
    title: "Policy engine evaluates rules",
    description: "KeyNetra resolves roles, relationships, ACLs, and policy conditions in one place."
  },
  {
    icon: CheckCircle2,
    title: "Decision is returned",
    description: "Your service receives an allow or deny decision with traceable metadata."
  }
] as const;

const useCases = [
  {
    icon: Blocks,
    title: "SaaS Platforms",
    description:
      "Manage user roles, teams, workspaces, entitlements, and resource-specific permissions without hardcoding product rules across services."
  },
  {
    icon: Network,
    title: "Marketplaces",
    description:
      "Model buyer, seller, operator, and resource relationships where access depends on ownership, delegation, and organizational boundaries."
  },
  {
    icon: LockKeyhole,
    title: "Fintech",
    description:
      "Enforce strict, auditable permission systems for approvals, operational actions, and sensitive data flows that need clear policy traceability."
  },
  {
    icon: GitBranch,
    title: "Internal Tools",
    description:
      "Control employee access to admin tools, support flows, and operational systems without proliferating one-off allow lists."
  }
];

const dxPoints = [
  "API-first design with a consistent decision contract",
  "Fast integration into existing services and gateways",
  "Language SDKs for Node.js, Go, and Python",
  "Designed for distributed systems and microservices"
];

export function HomeExperience() {
  return (
    <main className="overflow-x-clip bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.06),transparent_26%),linear-gradient(180deg,#030816_0%,#07101d_35%,#0a1425_100%)] text-white">
      <HeroScene />
      <ProblemScene />
      <FeatureScene />
      <ArchitectureScene />
      <CodeScene />
      <UseCasesScene />
      <DeveloperExperienceScene />
      <FinalCtaScene />
    </main>
  );
}

function HeroScene() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mouseX = useMotionValue(0.5);
  const mouseY = useMotionValue(0.5);
  const smoothX = useSpring(mouseX, { stiffness: 120, damping: 20, mass: 0.5 });
  const smoothY = useSpring(mouseY, { stiffness: 120, damping: 20, mass: 0.5 });
  const lightX = useTransform(smoothX, [0, 1], ["20%", "80%"]);
  const lightY = useTransform(smoothY, [0, 1], ["22%", "78%"]);
  const spotlight = useMotionTemplate`radial-gradient(circle at ${lightX} ${lightY}, rgba(59,130,246,0.22), transparent 30%)`;
  const xShift = useTransform(smoothX, [0, 1], [-18, 18]);
  const yShift = useTransform(smoothY, [0, 1], [-14, 14]);

  const nodes = useMemo(
    () => [
      { x: 16, y: 30, label: "User" },
      { x: 34, y: 48, label: "App" },
      { x: 58, y: 40, label: "KeyNetra" },
      { x: 80, y: 28, label: "Decision" },
      { x: 72, y: 64, label: "Policy" },
      { x: 44, y: 70, label: "Audit" }
    ],
    []
  );

  return (
    <section
      ref={containerRef}
      className="relative flex min-h-screen items-center overflow-hidden"
      onMouseMove={(event) => {
        const rect = containerRef.current?.getBoundingClientRect();
        if (!rect) return;
        mouseX.set((event.clientX - rect.left) / rect.width);
        mouseY.set((event.clientY - rect.top) / rect.height);
      }}
    >
      <div className="absolute inset-0 bg-hero-grid bg-[size:54px_54px] opacity-[0.12]" />
      <motion.div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(circle at 20% 20%, rgba(34,211,238,0.1), transparent 22%), radial-gradient(circle at 78% 16%, rgba(59,130,246,0.14), transparent 24%), linear-gradient(135deg, rgba(11,31,58,0.96), rgba(7,16,29,0.92))"
        }}
      />
      <motion.div className="absolute inset-0" style={{ background: spotlight }} />
      <motion.div
        className="absolute inset-x-0 top-0 h-[46vh] bg-[radial-gradient(circle_at_center,rgba(59,130,246,0.15),transparent_55%)]"
        style={{ x: xShift, y: yShift }}
      />

      <div className="relative mx-auto grid min-h-screen max-w-7xl items-center gap-16 px-4 py-28 sm:px-6 lg:grid-cols-[0.95fr,1.05fr] lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.42, ease: "easeInOut" }}
          className="z-10"
        >
          <Badge className="border-cyan-400/20 bg-cyan-400/10 text-cyan-100">
            Scene 1 • Immersion
          </Badge>
          <h1 className="mt-8 max-w-4xl text-6xl font-semibold leading-[0.94] tracking-[-0.05em] text-white sm:text-7xl xl:text-[6.4rem]">
            Authorization Infrastructure for Modern Applications
          </h1>
          <p className="mt-8 max-w-xl text-xl leading-8 text-slate-300">
            Stop hardcoding permissions. Move authorization into a dedicated,
            scalable system.
          </p>
          <p className="mt-5 text-sm font-medium uppercase tracking-[0.24em] text-cyan-100/85">
            Built for distributed systems and microservices
          </p>
          <div className="mt-10 flex flex-col gap-4 sm:flex-row">
            <MagneticAction href="/signup" variant="primary">
              Get Started
            </MagneticAction>
            <MagneticAction href="/docs" variant="secondary">
              View Docs
            </MagneticAction>
          </div>
        </motion.div>

        <motion.div
          className="relative h-[60vh] min-h-[480px]"
          style={{ x: xShift, y: yShift }}
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.46, ease: "easeInOut", delay: 0.08 }}
        >
          <svg viewBox="0 0 100 100" className="absolute inset-0 h-full w-full">
            <defs>
              <linearGradient id="flow-line" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="rgba(34,211,238,0.2)" />
                <stop offset="50%" stopColor="rgba(59,130,246,0.95)" />
                <stop offset="100%" stopColor="rgba(34,211,238,0.2)" />
              </linearGradient>
              <filter id="glow">
                <feGaussianBlur stdDeviation="0.8" result="coloredBlur" />
                <feMerge>
                  <feMergeNode in="coloredBlur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {[
              [0, 1],
              [1, 2],
              [2, 3],
              [2, 4],
              [1, 5],
              [5, 4]
            ].map(([from, to], index) => (
              <g key={`${from}-${to}`}>
                <line
                  x1={nodes[from].x}
                  y1={nodes[from].y}
                  x2={nodes[to].x}
                  y2={nodes[to].y}
                  stroke="rgba(148,163,184,0.26)"
                  strokeWidth="0.35"
                />
                <motion.line
                  x1={nodes[from].x}
                  y1={nodes[from].y}
                  x2={nodes[to].x}
                  y2={nodes[to].y}
                  stroke="url(#flow-line)"
                  strokeWidth="0.6"
                  strokeLinecap="round"
                  filter="url(#glow)"
                  initial={{ pathLength: 0, opacity: 0.4 }}
                  animate={{ pathLength: [0.15, 1, 0.15], opacity: [0.2, 1, 0.2] }}
                  transition={{
                    duration: 3.8,
                    delay: index * 0.28,
                    repeat: Infinity,
                    ease: "easeInOut"
                  }}
                />
              </g>
            ))}

            {nodes.map((node, index) => (
              <g key={node.label}>
                <motion.circle
                  cx={node.x}
                  cy={node.y}
                  r="4.1"
                  fill="rgba(11,31,58,0.95)"
                  stroke="rgba(34,211,238,0.38)"
                  strokeWidth="0.3"
                  animate={{ scale: [1, 1.14, 1] }}
                  transition={{
                    duration: 2.4,
                    delay: index * 0.22,
                    repeat: Infinity,
                    ease: "easeInOut"
                  }}
                />
                <circle
                  cx={node.x}
                  cy={node.y}
                  r="1.5"
                  fill="rgba(125,211,252,1)"
                  filter="url(#glow)"
                />
                <text
                  x={node.x}
                  y={node.y + 8.5}
                  textAnchor="middle"
                  fill="rgba(226,232,240,0.86)"
                  fontSize="3.2"
                  style={{ letterSpacing: "0.12em", textTransform: "uppercase" }}
                >
                  {node.label}
                </text>
              </g>
            ))}
          </svg>

          <motion.div
            className="absolute left-[12%] top-[16%] rounded-full bg-white/6 px-4 py-2 text-xs uppercase tracking-[0.24em] text-cyan-100 backdrop-blur-md"
            animate={{ y: [0, -8, 0] }}
            transition={{ duration: 3.4, repeat: Infinity, ease: "easeInOut" }}
          >
            user
          </motion.div>
          <motion.div
            className="absolute right-[8%] top-[46%] rounded-full bg-white/6 px-4 py-2 text-xs uppercase tracking-[0.24em] text-blue-100 backdrop-blur-md"
            animate={{ y: [0, 10, 0] }}
            transition={{ duration: 4.1, repeat: Infinity, ease: "easeInOut" }}
          >
            allow / deny
          </motion.div>
          <div className="absolute bottom-[14%] left-[15%] right-[18%] rounded-[2rem] border border-white/8 bg-white/5 px-6 py-5 backdrop-blur-xl">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">
              Live authorization flow
            </p>
            <p className="mt-3 font-mono text-sm text-slate-200">
              User → App → KeyNetra → Decision
            </p>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

function ProblemScene() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"]
  });
  const headlineY = useTransform(scrollYProgress, [0, 1], [70, -70]);

  return (
    <section ref={ref} className="relative min-h-screen bg-[linear-gradient(180deg,#07101d_0%,#091422_100%)]">
      <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(148,163,184,0.06)_1px,transparent_1px)] bg-[size:140px_100%] opacity-20" />
      <div className="mx-auto grid min-h-screen max-w-7xl gap-10 px-4 py-24 sm:px-6 lg:grid-cols-[0.92fr,1.08fr] lg:px-8">
        <motion.div style={{ y: headlineY }} className="lg:sticky lg:top-28 lg:self-start">
          <Badge className="border-rose-400/15 bg-rose-400/10 text-rose-100">
            Scene 2 • Tension
          </Badge>
          <h2 className="mt-8 text-5xl font-semibold leading-[0.95] tracking-[-0.04em] text-white sm:text-6xl">
            Stop hardcoding permissions.
          </h2>
          <p className="mt-8 max-w-lg text-lg leading-8 text-slate-300">
            Authorization fails quietly. One local shortcut becomes a system-wide
            inconsistency once services, teams, and exceptions start multiplying.
          </p>
        </motion.div>
        <div className="space-y-5 py-4 lg:py-20">
          {problems.map((problem, index) => (
            <motion.div
              key={problem}
              initial={{ opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.34, delay: index * 0.05, ease: "easeInOut" }}
              className="relative overflow-hidden rounded-[2rem] bg-white/[0.035] px-6 py-7 backdrop-blur-sm"
            >
              <div className="absolute inset-y-0 left-0 w-px bg-[linear-gradient(180deg,transparent,rgba(34,211,238,0.75),transparent)]" />
              <div className="flex items-start gap-5">
                <span className="mt-1 text-xs uppercase tracking-[0.24em] text-cyan-200/80">
                  0{index + 1}
                </span>
                <p className="max-w-2xl text-lg leading-8 text-slate-200">{problem}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

function FeatureScene() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end end"]
  });
  const activeIndex = useTransform(scrollYProgress, (value) =>
    Math.min(features.length - 1, Math.floor(value * features.length))
  );

  return (
    <section ref={ref} className="relative h-[460vh] bg-[#081321]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.1),transparent_22%),linear-gradient(180deg,rgba(3,8,20,0.2),rgba(3,8,20,0.4))]" />
      <div className="sticky top-0 flex min-h-screen items-center overflow-hidden">
        <div className="mx-auto grid w-full max-w-7xl gap-12 px-4 py-24 sm:px-6 lg:grid-cols-[0.86fr,1.14fr] lg:px-8">
          <div>
            <Badge className="border-cyan-400/18 bg-cyan-400/10 text-cyan-100">
              Scene 3 • System Emerges
            </Badge>
            <h2 className="mt-8 text-5xl font-semibold leading-[0.95] tracking-[-0.04em] text-white sm:text-6xl">
              Applications stop deciding permissions.
            </h2>
            <p className="mt-8 max-w-lg text-lg leading-8 text-slate-300">
              They ask KeyNetra. Scroll through the system and watch each capability
              become part of one authorization runtime.
            </p>
            <div className="mt-12 space-y-5">
              {features.map((feature, index) => (
                <FeatureCopy
                  key={feature.title}
                  feature={feature}
                  index={index}
                  activeIndex={activeIndex}
                />
              ))}
            </div>
          </div>
          <FeatureVisual activeIndex={activeIndex} />
        </div>
      </div>
    </section>
  );
}

function FeatureCopy({
  feature,
  index,
  activeIndex
}: {
  feature: Feature;
  index: number;
  activeIndex: MotionValue<number>;
}) {
  const opacity = useTransform(activeIndex, (value) => (value === index ? 1 : 0.35));
  const x = useTransform(activeIndex, (value) => (value === index ? 0 : 18));

  return (
    <motion.div style={{ opacity, x }} className="relative pl-8">
      <div className="absolute left-0 top-1 h-full w-px bg-[linear-gradient(180deg,rgba(148,163,184,0.2),rgba(34,211,238,0.5),rgba(148,163,184,0.2))]" />
      <feature.icon className="mb-4 h-5 w-5 text-cyan-300" />
      <h3 className="text-2xl font-semibold text-white">{feature.title}</h3>
      <p className="mt-3 text-sm font-medium leading-7 text-slate-200">{feature.summary}</p>
      <p className="mt-3 max-w-xl text-sm leading-7 text-slate-400">{feature.details}</p>
    </motion.div>
  );
}

function FeatureVisual({ activeIndex }: { activeIndex: MotionValue<number> }) {
  return (
    <div className="relative hidden min-h-[560px] lg:block">
      <div className="absolute inset-0 rounded-[3rem] bg-[radial-gradient(circle_at_center,rgba(59,130,246,0.12),transparent_42%)] blur-2xl" />
      <div className="absolute inset-0 rounded-[3rem] bg-[linear-gradient(180deg,rgba(255,255,255,0.02),rgba(255,255,255,0))]" />
      <div className="absolute left-[10%] top-[12%] h-[76%] w-[76%] rounded-full border border-white/8" />
      <div className="absolute left-[18%] top-[20%] h-[60%] w-[60%] rounded-full border border-white/6" />
      {features.map((feature, index) => (
        <FeatureVisualState
          key={feature.title}
          feature={feature}
          index={index}
          activeIndex={activeIndex}
        />
      ))}
    </div>
  );
}

function FeatureVisualState({
  feature,
  index,
  activeIndex
}: {
  feature: Feature;
  index: number;
  activeIndex: MotionValue<number>;
}) {
  const opacity = useTransform(activeIndex, (value) => (value === index ? 1 : 0));
  const scale = useTransform(activeIndex, (value) => (value === index ? 1 : 0.92));

  return (
    <motion.div style={{ opacity, scale }} className="absolute inset-0 flex items-center justify-center">
      <div className="relative flex h-[440px] w-[440px] items-center justify-center">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 16, repeat: Infinity, ease: "linear" }}
          className="absolute inset-0 rounded-full border border-cyan-400/15"
        />
        <motion.div
          animate={{ rotate: -360 }}
          transition={{ duration: 21, repeat: Infinity, ease: "linear" }}
          className="absolute inset-[52px] rounded-full border border-blue-400/15"
        />
        <div className="absolute inset-[120px] rounded-full bg-[radial-gradient(circle_at_center,rgba(34,211,238,0.16),rgba(59,130,246,0.08),transparent_70%)] blur-xl" />
        <div className="absolute inset-[132px] rounded-full border border-white/10 bg-[#07101d]/80 backdrop-blur-xl" />
        <div className="relative z-10 max-w-[240px] text-center">
          <feature.icon className="mx-auto h-10 w-10 text-cyan-300" />
          <p className="mt-6 text-xs uppercase tracking-[0.28em] text-cyan-100/80">
            {feature.signal}
          </p>
          <h4 className="mt-4 text-3xl font-semibold tracking-tight text-white">
            {feature.title}
          </h4>
        </div>
        {[0, 1, 2, 3].map((item) => (
          <motion.div
            key={item}
            className="absolute left-1/2 top-1/2 h-3 w-3 rounded-full bg-cyan-300 shadow-[0_0_20px_rgba(34,211,238,0.8)]"
            style={{
              x: Math.cos((item / 4) * Math.PI * 2) * 180,
              y: Math.sin((item / 4) * Math.PI * 2) * 180
            }}
            animate={{ scale: [1, 1.35, 1], opacity: [0.55, 1, 0.55] }}
            transition={{ duration: 2.6, delay: item * 0.2, repeat: Infinity }}
          />
        ))}
      </div>
    </motion.div>
  );
}

function ArchitectureScene() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end end"]
  });
  const activeIndex = useTransform(scrollYProgress, (value) =>
    Math.min(architectureSteps.length - 1, Math.floor(value * architectureSteps.length))
  );

  return (
    <section ref={ref} className="relative h-[320vh] bg-[linear-gradient(180deg,#091422_0%,#07101d_100%)]">
      <div className="sticky top-0 flex min-h-screen items-center">
        <div className="mx-auto grid w-full max-w-7xl gap-12 px-4 py-20 sm:px-6 lg:grid-cols-[1.04fr,0.96fr] lg:px-8">
          <div>
            <Badge className="border-blue-400/18 bg-blue-400/10 text-blue-100">
              Scene 4 • Animated System
            </Badge>
            <h2 className="mt-8 text-5xl font-semibold leading-[0.95] tracking-[-0.04em] text-white sm:text-6xl">
              Architecture builds as you scroll.
            </h2>
            <p className="mt-8 max-w-xl text-lg leading-8 text-slate-300">
              Access flows through one predictable path. Each step is explicit,
              traceable, and designed for services rather than UI-layer hacks.
            </p>
            <div className="mt-12 space-y-5">
              {architectureSteps.map((step, index) => (
                <ArchitectureStep
                  key={step.title}
                  step={step}
                  index={index}
                  activeIndex={activeIndex}
                />
              ))}
            </div>
          </div>

          <div className="relative hidden min-h-[560px] items-center justify-center lg:flex">
            <div className="absolute inset-0 rounded-[3rem] bg-[radial-gradient(circle_at_center,rgba(34,211,238,0.1),transparent_40%)] blur-3xl" />
            {[0, 1, 2, 3].map((_, index) => (
              <ArchitectureNode
                key={architectureSteps[index].title}
                label={architectureSteps[index].title}
                index={index}
                activeIndex={activeIndex}
                x={index === 0 ? "8%" : index === 1 ? "28%" : index === 2 ? "52%" : "76%"}
                y={index % 2 === 0 ? "44%" : "28%"}
              />
            ))}
            {[0, 1, 2].map((line) => (
              <ArchitectureLine key={line} line={line} activeIndex={activeIndex} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function ArchitectureStep({
  step,
  index,
  activeIndex
}: {
  step: (typeof architectureSteps)[number];
  index: number;
  activeIndex: MotionValue<number>;
}) {
  const opacity = useTransform(activeIndex, (value) => (value === index ? 1 : 0.38));
  const x = useTransform(activeIndex, (value) => (value === index ? 0 : 14));

  return (
    <motion.div style={{ opacity, x }} className="relative pl-8">
      <div className="absolute left-0 top-0 h-full w-px bg-[linear-gradient(180deg,rgba(59,130,246,0),rgba(59,130,246,0.8),rgba(59,130,246,0))]" />
      <step.icon className="mb-3 h-5 w-5 text-cyan-300" />
      <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Step {index + 1}</p>
      <h3 className="mt-3 text-2xl font-semibold text-white">{step.title}</h3>
      <p className="mt-3 max-w-xl text-sm leading-7 text-slate-400">{step.description}</p>
    </motion.div>
  );
}

function ArchitectureLine({
  line,
  activeIndex
}: {
  line: number;
  activeIndex: MotionValue<number>;
}) {
  const opacity = useTransform(activeIndex, (value) => (value >= line + 1 ? 1 : 0.18));

  return (
    <motion.div
      className="absolute top-[42%] h-px bg-[linear-gradient(90deg,rgba(34,211,238,0.1),rgba(59,130,246,0.95),rgba(34,211,238,0.1))]"
      style={{
        left: `${17 + line * 23}%`,
        width: "17%",
        opacity
      }}
    />
  );
}

function ArchitectureNode({
  label,
  index,
  activeIndex,
  x,
  y
}: {
  label: string;
  index: number;
  activeIndex: MotionValue<number>;
  x: string;
  y: string;
}) {
  const opacity = useTransform(activeIndex, (value) => (value >= index ? 1 : 0.25));
  const scale = useTransform(activeIndex, (value) => (value === index ? 1 : 0.92));

  return (
    <motion.div
      className="absolute -translate-x-1/2 -translate-y-1/2"
      style={{ left: x, top: y, opacity, scale }}
    >
      <div className="rounded-[1.8rem] bg-white/[0.045] px-5 py-4 shadow-[0_18px_50px_rgba(0,0,0,0.24)] backdrop-blur-xl">
        <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Node {index + 1}</p>
        <p className="mt-2 text-sm font-medium text-white">{label}</p>
      </div>
    </motion.div>
  );
}

function CodeScene() {
  return (
    <section className="relative flex min-h-screen items-center bg-[linear-gradient(180deg,#07101d_0%,#0a1425_100%)]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_12%_18%,rgba(34,211,238,0.08),transparent_18%),radial-gradient(circle_at_78%_24%,rgba(59,130,246,0.14),transparent_22%)]" />
      <div className="mx-auto grid w-full max-w-7xl gap-14 px-4 py-24 sm:px-6 lg:grid-cols-[0.88fr,1.12fr] lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.34, ease: "easeInOut" }}
        >
          <Badge className="border-cyan-400/18 bg-cyan-400/10 text-cyan-100">
            Scene 5 • Code Interaction
          </Badge>
          <h2 className="mt-8 text-5xl font-semibold leading-[0.95] tracking-[-0.04em] text-white sm:text-6xl">
            Check access in a single call.
          </h2>
          <p className="mt-8 max-w-xl text-lg leading-8 text-slate-300">
            Input enters through your service. KeyNetra evaluates roles, policies,
            and relationships. Output returns as an allow or deny decision.
          </p>
          <div className="mt-12 space-y-5">
            {[
              "Input: user, resource, action, and request context",
              "Evaluation: one policy engine resolves access centrally",
              "Output: deterministic decision with traceable metadata"
            ].map((step, index) => (
              <motion.div
                key={step}
                initial={{ opacity: 0, x: -18 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: "-80px" }}
                transition={{ duration: 0.28, delay: index * 0.05, ease: "easeInOut" }}
                className="group flex items-start gap-4"
              >
                <div className="mt-1 rounded-full bg-cyan-400/12 p-2 text-cyan-300 transition group-hover:scale-110">
                  <ArrowRight className="h-4 w-4" />
                </div>
                <p className="text-base leading-8 text-slate-300">{step}</p>
              </motion.div>
            ))}
          </div>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.38, delay: 0.08, ease: "easeInOut" }}
        >
          <CodeTabs />
        </motion.div>
      </div>
    </section>
  );
}

function UseCasesScene() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end end"]
  });
  const x = useTransform(scrollYProgress, [0, 1], ["0%", "-52%"]);

  return (
    <section ref={ref} className="relative h-[260vh] bg-[linear-gradient(180deg,#0a1425_0%,#07101d_100%)]">
      <div className="sticky top-0 flex min-h-screen items-center overflow-hidden">
        <div className="mx-auto w-full max-w-7xl px-4 py-24 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.34, ease: "easeInOut" }}
            className="mb-16 max-w-3xl"
          >
            <Badge className="border-blue-400/18 bg-blue-400/10 text-blue-100">
              Scene 6 • Use Cases
            </Badge>
            <h2 className="mt-8 text-5xl font-semibold leading-[0.95] tracking-[-0.04em] text-white sm:text-6xl">
              One system. Different authorization realities.
            </h2>
          </motion.div>
          <motion.div style={{ x }} className="flex gap-6">
            {useCases.map((item) => (
              <motion.div
                key={item.title}
                whileHover={{ y: -8, scale: 1.01 }}
                transition={{ duration: 0.24, ease: "easeInOut" }}
                className="relative min-h-[430px] w-[78vw] max-w-[520px] shrink-0 overflow-hidden rounded-[2.5rem] bg-white/[0.045] p-8 shadow-[0_28px_80px_rgba(0,0,0,0.28)] backdrop-blur-xl"
              >
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.18),transparent_42%)]" />
                <div className="relative">
                  <div className="flex items-center justify-between">
                    <item.icon className="h-8 w-8 text-cyan-300" />
                    <span className="text-xs uppercase tracking-[0.24em] text-slate-500">
                      scenario
                    </span>
                  </div>
                  <h3 className="mt-8 text-3xl font-semibold tracking-tight text-white">
                    {item.title}
                  </h3>
                  <p className="mt-5 text-base leading-8 text-slate-300">{item.description}</p>
                  <div className="mt-10 h-px w-full bg-[linear-gradient(90deg,rgba(34,211,238,0),rgba(34,211,238,0.65),rgba(34,211,238,0))]" />
                  <p className="mt-6 font-mono text-xs uppercase tracking-[0.24em] text-slate-400">
                    resource graph active
                  </p>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </div>
    </section>
  );
}

function DeveloperExperienceScene() {
  return (
    <section className="relative flex min-h-screen items-center bg-[linear-gradient(180deg,#07101d_0%,#06101b_100%)]">
      <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(148,163,184,0.06)_1px,transparent_1px),linear-gradient(180deg,rgba(148,163,184,0.04)_1px,transparent_1px)] bg-[size:120px_100%,100%_120px] opacity-15" />
      <div className="mx-auto grid w-full max-w-7xl gap-14 px-4 py-24 sm:px-6 lg:grid-cols-[0.92fr,1.08fr] lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.34, ease: "easeInOut" }}
        >
          <Badge className="border-cyan-400/18 bg-cyan-400/10 text-cyan-100">
            Scene 7 • Developer Experience
          </Badge>
          <h2 className="mt-8 text-5xl font-semibold leading-[0.95] tracking-[-0.04em] text-white sm:text-6xl">
            API-first. Fast to wire in. Built to run anywhere.
          </h2>
          <p className="mt-8 max-w-xl text-lg leading-8 text-slate-300">
            KeyNetra is designed like infrastructure software, not a UI wrapper.
            Services integrate once and ask the same authorization question everywhere.
          </p>
          <div className="mt-10">
            <Link
              href="/open-source"
              className="inline-flex items-center gap-2 text-sm font-medium text-cyan-200 transition hover:translate-x-1 hover:text-white"
            >
              Explore on GitHub
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </motion.div>
        <div className="grid gap-5">
          {dxPoints.map((point, index) => (
            <motion.div
              key={point}
              initial={{ opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.32, delay: index * 0.05, ease: "easeInOut" }}
              className="relative rounded-[2rem] bg-white/[0.04] px-6 py-6 backdrop-blur-xl"
            >
              <div className="absolute inset-y-0 left-0 w-px bg-[linear-gradient(180deg,rgba(59,130,246,0),rgba(34,211,238,0.9),rgba(59,130,246,0))]" />
              <p className="pl-4 text-base leading-8 text-slate-200">{point}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

function FinalCtaScene() {
  return (
    <section className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[linear-gradient(180deg,#06101b_0%,#040a14_100%)]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(59,130,246,0.18),transparent_30%),radial-gradient(circle_at_50%_80%,rgba(34,211,238,0.1),transparent_24%)]" />
      <motion.div
        initial={{ opacity: 0, scale: 0.97, y: 16 }}
        whileInView={{ opacity: 1, scale: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.38, ease: "easeInOut" }}
        className="relative mx-auto max-w-5xl px-4 py-24 text-center sm:px-6 lg:px-8"
      >
        <Badge className="border-cyan-400/18 bg-cyan-400/10 text-cyan-100">
          Scene 8 • Final CTA
        </Badge>
        <h2 className="mt-8 text-6xl font-semibold leading-[0.94] tracking-[-0.05em] text-white sm:text-7xl xl:text-[5.8rem]">
          Start building with KeyNetra today
        </h2>
        <p className="mx-auto mt-8 max-w-2xl text-xl leading-8 text-slate-300">
          Centralize authorization before it becomes permanent platform debt.
        </p>
        <div className="mt-12 flex flex-col justify-center gap-4 sm:flex-row">
          <MagneticAction href="/signup" variant="primary">
            Get Started
          </MagneticAction>
          <MagneticAction href="/docs" variant="secondary">
            View Docs
          </MagneticAction>
        </div>
      </motion.div>
    </section>
  );
}

function MagneticAction({
  href,
  children,
  variant
}: {
  href: string;
  children: ReactNode;
  variant: "primary" | "secondary";
}) {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springX = useSpring(x, { stiffness: 180, damping: 16, mass: 0.4 });
  const springY = useSpring(y, { stiffness: 180, damping: 16, mass: 0.4 });

  return (
    <motion.div
      style={{ x: springX, y: springY }}
      onMouseMove={(event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        x.set((event.clientX - rect.left - rect.width / 2) * 0.12);
        y.set((event.clientY - rect.top - rect.height / 2) * 0.12);
      }}
      onMouseLeave={() => {
        x.set(0);
        y.set(0);
      }}
      whileTap={{ scale: 0.98 }}
      className="inline-flex"
    >
      <Link href={href}>
        <Button
          size="lg"
          variant={variant === "primary" ? "default" : "secondary"}
          className={cn(
            "group relative overflow-hidden rounded-full px-7",
            variant === "secondary" &&
              "border-white/15 bg-white/8 text-white hover:bg-white/12 hover:text-white"
          )}
        >
          <span className="relative z-10 inline-flex items-center gap-2">
            {children}
            <ArrowRight className="h-4 w-4 transition-transform duration-300 ease-in-out group-hover:translate-x-0.5" />
          </span>
          <span className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.18),transparent_58%)] opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
        </Button>
      </Link>
    </motion.div>
  );
}
