const NATION_LABEL = { IN: "India", BR: "Brazil", ZA: "South Africa" };

export default function PlotIndex({ plots, selectedId, onSelect }) {
  return (
    <nav className="plot-index" aria-label="Plots">
      <div className="plot-index__brand">
        <span className="plot-index__mark">⟡</span>
        <div>
          <div className="plot-index__title">AgriN Twin</div>
          <div className="plot-index__subtitle">Field Ledger</div>
        </div>
      </div>

      <div className="plot-index__list-label">Registered plots</div>
      <ul className="plot-index__list">
        {plots.map((plot) => (
          <li key={plot.id}>
            <button
              className={
                "plot-index__item" +
                (plot.id === selectedId ? " plot-index__item--active" : "")
              }
              onClick={() => onSelect(plot.id)}
            >
              <span className="plot-index__item-name">{plot.name}</span>
              <span className="plot-index__item-meta">
                {plot.primary_crop} · {NATION_LABEL[plot.nation] || plot.nation}
              </span>
            </button>
          </li>
        ))}
        {plots.length === 0 && (
          <li className="plot-index__empty">
            No plots yet. Seed demo data or register one via the API.
          </li>
        )}
      </ul>
    </nav>
  );
}
