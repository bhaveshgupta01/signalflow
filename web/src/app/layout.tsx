import type { Metadata } from "next";
import { Sora, Inter } from "next/font/google";
import "./globals.css";
import Nav from "@/components/nav";

const sora = Sora({
  variable: "--font-sora",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "SignalFlow — AI Trading Agent | Powered by Boba",
  description:
    "Event-driven AI crypto trading agent powered by Boba Agents MCP",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${sora.variable} ${inter.variable} h-full antialiased`}
    >
      <body className="min-h-full flex bg-sf-bg">
        <Nav />
        <main className="flex-1 overflow-y-auto lg:pt-0 pt-14">
          {children}
        </main>
      </body>
    </html>
  );
}
