import { useEffect, useState, useCallback } from "react";
import PlotIndex from "./components/PlotIndex";
import TwinEntry from "./components/TwinEntry";
import FederationStrip from "./components/FederationStrip";
import { api } from "./lib/api";
import "./app.css";

export default function App() {
  const [plots, setPlots] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [twin, setTwin] = useState(null);
  const [nodes, setNodes] = useState([]);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    api
      .listPlots()
      .then((data) => {
        setPlots(data);
        if (data.length > 0) setSelectedId(data[0].id);
      })
      .catch(() => setLoadError(true));

    api.federationNodes().then(setNodes).catch(() => {});
  }, []);

  const loadTwin = useCallback(() => {
    if (!selectedId) return;
    api.getTwin(selectedId).then(setTwin).catch(() => setLoadError(true));
  }, [selectedId]);

  useEffect(() => {
    loadTwin();
  }, [loadTwin]);

  if (loadError) {
    return (
      <div className="boot-error">
        <h1>Can't reach the AgriN Twin backend</h1>
        <p>
          Start it with <code>uvicorn app.main:app --reload</code> in{" "}
          <code>backend/</code>, then reload this page. Run{" "}
          <code>python seed_demo_data.py</code> first for sample plots.
        </p>
      </div>
    );
  }

  return (
    <div className="shell">
      <div className="shell__body">
        <PlotIndex plots={plots} selectedId={selectedId} onSelect={setSelectedId} />
        <main className="shell__main">
          {twin ? (
            <TwinEntry twin={twin} onRefresh={loadTwin} />
          ) : (
            <p className="empty-note" style={{ padding: "2rem" }}>
              {plots.length === 0
                ? "No plots registered yet."
                : "Select a plot from the ledger."}
            </p>
          )}
        </main>
      </div>
      <FederationStrip nodes={nodes} />
    </div>
  );
}
