import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="relative flex h-screen overflow-hidden bg-background">
      {/* Ambient background: dot grid + animated aurora blobs */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 bg-dot-pattern mask-fade-bottom opacity-60"
      />
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10 bg-noise opacity-[0.05] mix-blend-overlay"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
      >
        <div className="animate-aurora absolute -right-40 -top-40 h-[28rem] w-[28rem] rounded-full bg-gradient-to-br from-primary/25 via-fuchsia-500/15 to-transparent blur-3xl" />
        <div
          className="animate-aurora absolute -bottom-40 -left-40 h-[26rem] w-[26rem] rounded-full bg-gradient-to-tr from-cyan-500/20 via-emerald-500/10 to-transparent blur-3xl"
          style={{ animationDelay: "3s" }}
        />
        <div
          className="animate-aurora absolute left-1/3 top-1/4 h-[20rem] w-[20rem] rounded-full bg-gradient-to-br from-violet-500/15 via-sky-500/10 to-transparent blur-3xl"
          style={{ animationDelay: "6s" }}
        />
      </div>

      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
