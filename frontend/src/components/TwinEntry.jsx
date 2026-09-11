import SoilTrajectoryChart from "./SoilTrajectoryChart";
import DiseaseScanPanel from "./DiseaseScanPanel";
import FieldAgentPanel from "./FieldAgentPanel";
import { api } from "../lib/api";

function trendLabel(trend) {
  if (trend === null || trend === undefined) return "first reading";
  const sign = trend > 0 ? "+" : "";
  return `${sign}${trend} since last`;
}

function componentBar(label, value, color) {
  return (
    <div className="component-bar" key={label}>
      <div className="component-bar__labels">
        <span>{label}</span>
        <span className="tabular">{Math.round(value)}</span>
      </div>
      <div className="component-bar__track">
        <div
          className="component-bar__fill"
          style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: color }}
        />
      </div>
    </div>
  );
}

export default function TwinEntry({ twin, onRefresh }) {
  const { plot, latest_sensor, latest_satellite, latest_disease_report, latest_soil_score, soil_score_history } = twin;

  async function handleRefreshSatellite() {
    await api.refreshSatellite(plot.id);
    onRefresh();
  }

  async function handleComputeScore() {
    await api.computeSoilScore(plot.id);
    onRefresh();
  }

  return (
    <article className="entry">
      <header className="entry__header">
        <div>
          <h1>{plot.name}</h1>
          <p className="entry__subtitle">
            {plot.primary_crop} · {plot.area_hectares} ha · {plot.nation}
            {plot.sensor_pod_id ? ` · pod ${plot.sensor_pod_id}` : ""}
          </p>
        </div>
      </header>

      <section className="entry__section entry__hero">
        <div className="hero-score">
          <span className="hero-score__eyebrow">Regenerative soil trajectory</span>
          <div className="hero-score__value tabular">
            {latest_soil_score ? Math.round(latest_soil_score.score) : "—"}
            <span className="hero-score__scale">/100</span>
          </div>
          <span className="hero-score__trend">
            {latest_soil_score ? trendLabel(latest_soil_score.trend_vs_previous) : "not yet computed"}
          </span>
          <button className="btn-outline" onClick={handleComputeScore}>
            Recompute score
          </button>
        </div>
        <div className="hero-chart">
          <SoilTrajectoryChart history={soil_score_history} />
        </div>
      </section>

      {latest_soil_score && (
        <section className="entry__section">
          <h3>What's driving the score</h3>
          <div className="component-bars">
            {componentBar("Vegetation vigor (NDVI)", latest_soil_score.vegetation_vigor_component, "#3f6b3b")}
            {componentBar("Moisture stability", latest_soil_score.moisture_stability_component, "#2f5d73")}
            {componentBar("Crop diversity", latest_soil_score.crop_diversity_component, "#a85426")}
          </div>
        </section>
      )}

      <section className="entry__section entry__readouts">
        <div className="readout">
          <div className="entry-row-header">
            <h3>Latest satellite pass</h3>
            <button className="btn-link" onClick={handleRefreshSatellite}>
              Pull new pass
            </button>
          </div>
          {latest_satellite ? (
            <dl className="readout__grid">
              <div>
                <dt>NDVI</dt>
                <dd className="tabular">{latest_satellite.ndvi}</dd>
              </div>
              <div>
                <dt>NDMI</dt>
                <dd className="tabular">{latest_satellite.ndmi ?? "—"}</dd>
              </div>
              <div>
                <dt>Land surface temp</dt>
                <dd className="tabular">{latest_satellite.land_surface_temp_c}°C</dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd>{latest_satellite.source}</dd>
              </div>
            </dl>
          ) : (
            <p className="empty-note">No satellite pass recorded yet.</p>
          )}
        </div>

        <div className="readout">
          <h3>Latest sensor reading</h3>
          {latest_sensor ? (
            <dl className="readout__grid">
              <div>
                <dt>Soil moisture</dt>
                <dd className="tabular">{latest_sensor.soil_moisture_pct}%</dd>
              </div>
              <div>
                <dt>Soil temp</dt>
                <dd className="tabular">{latest_sensor.soil_temp_c}°C</dd>
              </div>
              <div>
                <dt>Air humidity</dt>
                <dd className="tabular">{latest_sensor.air_humidity_pct}%</dd>
              </div>
              <div>
                <dt>Conductivity</dt>
                <dd className="tabular">{latest_sensor.soil_conductivity_us_cm} µS/cm</dd>
              </div>
            </dl>
          ) : (
            <p className="empty-note">No sensor pod data yet.</p>
          )}
        </div>
      </section>

      <section className="entry__section">
        <DiseaseScanPanel
          plotId={plot.id}
          latestReport={latest_disease_report}
          onScanned={onRefresh}
        />
      </section>

      <section className="entry__section">
        <FieldAgentPanel plotId={plot.id} farmerId={plot.farmer_id} />
      </section>
    </article>
  );
}
