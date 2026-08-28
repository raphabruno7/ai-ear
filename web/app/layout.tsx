import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "call-copilot",
  description: "Listening voice copilot — dashboard",
};

const NAV = [
  { href: "/", label: "Sessions" },
  { href: "/eval", label: "Eval" },
  { href: "/costs", label: "Costs" },
  { href: "/demo-scheduler", label: "Demo scheduler" },
] as const;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
        <header className="border-b border-zinc-200 dark:border-zinc-800">
          <nav className="mx-auto flex max-w-4xl items-center gap-5 px-6 py-3 text-sm">
            <span className="font-semibold">call-copilot</span>
            {NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
              >
                {n.label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
