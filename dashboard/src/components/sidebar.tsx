import Link from "next/link";
import { Newspaper, BarChart3, Zap, DollarSign, Globe, Settings } from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: BarChart3 },
  { href: "/news", label: "News", icon: Newspaper },
  { href: "/flash", label: "Flash", icon: Zap },
  { href: "/earnings", label: "Earnings", icon: DollarSign },
  { href: "/macro", label: "Macro", icon: Globe },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  return (
    <aside className="flex h-screen w-56 flex-col border-r bg-card">
      <div className="flex h-14 items-center border-b px-4">
        <Newspaper className="mr-2 h-5 w-5 text-primary" />
        <span className="text-lg font-bold">NewsAgent</span>
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="border-t p-4">
        <p className="text-xs text-muted-foreground">Powered by AI</p>
      </div>
    </aside>
  );
}