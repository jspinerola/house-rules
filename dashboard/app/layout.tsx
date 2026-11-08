import type { ReactNode } from "react";

export const metadata = { title: "House Rules - house view" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "ui-monospace, monospace", margin: 16 }}>{children}</body>
    </html>
  );
}
