const NATION_LABEL = { IN: "India", BR: "Brazil", ZA: "South Africa" };

export default function FederationStrip({ nodes }) {
  return (
    <footer className="federation-strip">
      <span className="federation-strip__label">BRICS model exchange</span>
      <div className="federation-strip__nodes">
        {nodes.map((n) => (
          <span key={n.node_id} className="federation-node">
            <span className="federation-node__dot" />
            {NATION_LABEL[n.nation] || n.nation}
            <span className="tabular federation-node__count">
              {n.models_published} update{n.models_published === 1 ? "" : "s"}
            </span>
          </span>
        ))}
        {nodes.length === 0 && (
          <span className="federation-strip__empty">No nodes have published yet.</span>
        )}
      </div>
    </footer>
  );
}
