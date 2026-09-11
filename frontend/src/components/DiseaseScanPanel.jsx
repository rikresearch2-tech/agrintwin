import { useRef, useState } from "react";
import { api } from "../lib/api";

export default function DiseaseScanPanel({ plotId, latestReport, onScanned }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  async function handleFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const report = await api.scanDisease(plotId, file);
      onScanned(report);
    } catch (err) {
      setError("Scan failed — check the backend is running.");
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  return (
    <div className="scan-panel">
      <div className="entry-row-header">
        <h3>Disease scan</h3>
        <button
          className="btn-link"
          onClick={() => inputRef.current?.click()}
          disabled={busy}
        >
          {busy ? "Diagnosing…" : "Upload leaf photo"}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          hidden
          onChange={handleFile}
        />
      </div>

      {error && <p className="error-note">{error}</p>}

      {latestReport ? (
        <div
          className={
            "scan-result" +
            (latestReport.is_healthy ? " scan-result--healthy" : " scan-result--alert")
          }
        >
          <div className="scan-result__label">
            {latestReport.predicted_label.replaceAll("_", " ")}
            <span className="tabular"> · {Math.round(latestReport.confidence * 100)}% confidence</span>
          </div>
          <p className="scan-result__action">{latestReport.recommended_action}</p>
        </div>
      ) : (
        <p className="empty-note">No scans yet for this plot.</p>
      )}
    </div>
  );
}
