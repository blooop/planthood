import './globals.css';

export const metadata = {
  title: 'Planthood Recipes',
  description: 'Interactive recipe timelines for Planthood meals',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <div className="container">
            <h1 className="site-title">
              <a href="/">Planthood Recipes</a>
            </h1>
            <p className="site-tagline">Interactive cooking timelines</p>
          </div>
        </header>

        <main className="site-main">
          <div className="container">
            {children}
          </div>
        </main>

        <footer className="site-footer">
          <div className="container">
            <p>
              Recipe data from <a href="https://planthood.co.uk" target="_blank" rel="noopener noreferrer">Planthood</a>
            </p>
            <p className="footer-note">
              Updated weekly via automated scraping and LLM parsing
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
