import "./globals.css";

export const metadata = {
  title: "Company Research Engine",
  description: "Source-backed GTM research for a company, with honest gaps.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
