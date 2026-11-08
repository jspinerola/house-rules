import type { ReactNode } from "react";
import { Onest } from "next/font/google";
import "./globals.css";

const onest = Onest({ subsets: ["latin"], variable: "--font-onest" });

export const metadata = { title: "House Rules", description: "Your household, on the same page about money." };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={onest.variable}>
      <body className="min-h-screen font-sans antialiased">{children}</body>
    </html>
  );
}
