"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  CalendarDays,
  Scissors,
  Users,
  FileText,
  Megaphone,
  Settings,
  LogOut,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/confirm-dialog";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/appointments", label: "Appointments", icon: CalendarDays },
  { href: "/dashboard/services", label: "Services", icon: Scissors },
  { href: "/dashboard/staff", label: "Staff", icon: Users },
  { href: "/dashboard/invoices", label: "Invoices", icon: FileText },
  { href: "/dashboard/broadcasts", label: "Broadcasts", icon: Megaphone },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { salon, isLoading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [signOutOpen, setSignOutOpen] = useState(false);

  useEffect(() => {
    if (!isLoading && !salon) {
      router.replace("/login");
    }
  }, [salon, isLoading, router]);

  if (isLoading || !salon) return null;

  return (
    <div className="flex min-h-screen bg-zinc-50">
      {/* Sidebar */}
      <aside className="flex w-56 flex-col border-r border-zinc-200 bg-white">
        {/* Logo */}
        <div className="flex items-center gap-2 px-4 py-4 border-b border-zinc-100">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-zinc-900 text-white font-bold text-xs">P</div>
          <span className="font-semibold text-sm tracking-tight">Ping</span>
        </div>

        {/* Salon name */}
        <div className="px-4 py-3 border-b border-zinc-100">
          <p className="text-xs text-zinc-400 font-medium uppercase tracking-wide">Signed in as</p>
          <p className="text-sm font-semibold text-zinc-900 truncate mt-0.5">{salon.salon_name}</p>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-2">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2.5 px-4 py-2.5 text-sm transition-colors",
                  active
                    ? "bg-zinc-100 text-zinc-900 font-semibold"
                    : "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-800"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Logout */}
        <div className="p-3 border-t border-zinc-100">
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start gap-2 text-zinc-500 hover:text-zinc-900"
            onClick={() => setSignOutOpen(true)}
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </Button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0 overflow-auto">
        {children}
      </main>

      <ConfirmDialog
        open={signOutOpen}
        onOpenChange={setSignOutOpen}
        title="Sign out"
        description="Are you sure you want to sign out of your dashboard?"
        confirmLabel="Sign out"
        onConfirm={() => { logout(); router.replace("/login"); }}
      />
    </div>
  );
}
