import "./globals.css";

export const metadata = {
  title: "YAP ENGINE",
  description: "RAG-powered document Q&A",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}