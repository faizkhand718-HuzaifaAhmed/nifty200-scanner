import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NIFTY 200 Opportunity Scanner",
  description: "Intraday technical analysis and paper trading dashboard - not investment advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
