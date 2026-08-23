/**
 * ErrorBoundary — global crash guard for the NAVIGUIDE React tree.
 *
 * Two rendering modes:
 *  - DEV  (import.meta.env.DEV): shows full stack + component stack so the
 *    developer can pinpoint the crashing component immediately.
 *  - PROD (production build): shows a minimal, user-friendly message + a
 *    reload button. No stack exposed.
 *
 * Rationale: MapLibre popups have historically crashed the whole SPA when
 * a child component accesses a missing `feature.properties.*` prop.
 * Wrapping the app in this boundary prevents the WhiteScreenOfDeath.
 */
import { Component } from "react";

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null, info: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Always log to the console — makes headless Playwright captures useful.
    console.error("[NAVIGUIDE:ErrorBoundary]", error, info?.componentStack);
    this.setState({ info });
  }

  handleReload = () => {
    // Try a soft recovery first: clear state and let React re-render.
    // If the same tree keeps crashing, the user clicks the same button again
    // which then triggers a hard reload as a fallback.
    if (this._softTried) {
      window.location.reload();
    } else {
      this._softTried = true;
      this.setState({ error: null, info: null });
    }
  };

  render() {
    const { error, info } = this.state;
    if (!error) return this.props.children;

    // Allow ?debug=1 in the URL to force the full dev-style diagnostic panel
    // even on production builds — useful for triaging user-reported crashes
    // without redeploying a dev build.
    const forceDebug =
      typeof window !== "undefined" &&
      /[?&]debug=1(?:&|$)/.test(window.location.search);

    // ── DEV or ?debug=1: full diagnostic panel ─────────────────────────────
    if (import.meta.env.DEV || forceDebug) {
      return (
        <div
          data-testid="error-boundary-dev"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 99999,
            background: "#0f172a",
            color: "#f1f5f9",
            padding: 24,
            overflow: "auto",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: 13,
            lineHeight: 1.5,
          }}
        >
          <div style={{ maxWidth: 960, margin: "0 auto" }}>
            <div style={{ color: "#f87171", fontSize: 20, fontWeight: 700, marginBottom: 4 }}>
              React crash — ErrorBoundary caught
            </div>
            <div style={{ color: "#94a3b8", marginBottom: 16 }}>
              (DEV mode — this panel is hidden in production builds.)
            </div>

            <div style={{ color: "#fbbf24", fontWeight: 600, marginBottom: 4 }}>
              {error.name || "Error"}: {error.message}
            </div>

            {error.stack && (
              <pre
                style={{
                  background: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: 8,
                  padding: 12,
                  overflow: "auto",
                  color: "#e2e8f0",
                  marginBottom: 16,
                  whiteSpace: "pre-wrap",
                }}
              >
                {error.stack}
              </pre>
            )}

            {info?.componentStack && (
              <>
                <div style={{ color: "#a5b4fc", fontWeight: 600, marginBottom: 4 }}>
                  Component stack
                </div>
                <pre
                  style={{
                    background: "#1e293b",
                    border: "1px solid #334155",
                    borderRadius: 8,
                    padding: 12,
                    overflow: "auto",
                    color: "#cbd5e1",
                    marginBottom: 16,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {info.componentStack}
                </pre>
              </>
            )}

            <button
              onClick={this.handleReload}
              data-testid="error-boundary-reload-btn"
              style={{
                background: "#2563eb",
                color: "white",
                border: 0,
                padding: "10px 18px",
                borderRadius: 8,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Try to recover / Reload
            </button>
          </div>
        </div>
      );
    }

    // ── PROD: minimal, user-friendly panel ────────────────────────────────
    return (
      <div
        data-testid="error-boundary-prod"
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 99999,
          background: "#0f172a",
          color: "#f1f5f9",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: 24,
          fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif",
        }}
      >
        <div style={{ maxWidth: 420, textAlign: "center" }}>
          <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 8 }}>
            Une erreur est survenue
          </div>
          <div style={{ color: "#94a3b8", fontSize: 14, marginBottom: 20, lineHeight: 1.5 }}>
            L&apos;application a rencontré un problème inattendu. Rechargez la page pour continuer.
          </div>
          <button
            onClick={this.handleReload}
            data-testid="error-boundary-reload-btn"
            style={{
              background: "#2563eb",
              color: "white",
              border: 0,
              padding: "10px 22px",
              borderRadius: 8,
              fontWeight: 600,
              cursor: "pointer",
              fontSize: 14,
            }}
          >
            Recharger la page
          </button>
        </div>
      </div>
    );
  }
}
