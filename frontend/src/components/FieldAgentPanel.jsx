import { useState } from "react";
import { api } from "../lib/api";

const LANGUAGES = [
  { code: "bn", label: "Bengali" },
  { code: "en", label: "English" },
  { code: "pt", label: "Portuguese" },
  { code: "zu", label: "isiZulu" },
];

export default function FieldAgentPanel({ plotId, farmerId }) {
  const [language, setLanguage] = useState("bn");
  const [transcript, setTranscript] = useState("");
  const [exchange, setExchange] = useState([]);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (!transcript.trim()) return;
    setBusy(true);
    const question = transcript;
    setTranscript("");
    try {
      const result = await api.voiceQuery({
        plot_id: plotId,
        farmer_id: farmerId,
        language,
        transcript: question,
        channel: "web",
      });
      setExchange((prev) => [...prev, { question, ...result }]);
    } catch {
      setExchange((prev) => [
        ...prev,
        { question, response_text: "The field agent is unreachable — check the backend.", intent: "error" },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="agent-panel">
      <div className="entry-row-header">
        <h3>Ask the field agent</h3>
        <select
          className="lang-select"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          aria-label="Language"
        >
          {LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>
      </div>

      <p className="agent-panel__hint">
        Works over voice or text, in the farmer's own language — same channel a WhatsApp
        or IVR call would use.
      </p>

      <div className="agent-panel__exchange">
        {exchange.map((turn, i) => (
          <div key={i} className="agent-turn">
            <p className="agent-turn__q">{turn.question}</p>
            <p className="agent-turn__a">{turn.response_text}</p>
          </div>
        ))}
      </div>

      <form onSubmit={submit} className="agent-panel__form">
        <input
          type="text"
          value={transcript}
          onChange={(e) => setTranscript(e.target.value)}
          placeholder="e.g. amar jomite ki jol dewa dorkar?"
          aria-label="Question for the field agent"
        />
        <button type="submit" disabled={busy}>
          {busy ? "Asking…" : "Ask"}
        </button>
      </form>
    </div>
  );
}
