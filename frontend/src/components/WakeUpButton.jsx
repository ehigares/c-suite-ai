/**
 * WakeUpButton — shown in the conversation header for every conversation.
 *
 * Checks whether RunPod endpoints in the council are alive. Auto-shows green
 * with an explanatory tooltip when no RunPod endpoints are present.
 *
 * Props:
 *   councilModels {Array} - Model objects from conversation.council_config.available_models
 *
 * States:
 *   auto-green  — No RunPod endpoints; always ready
 *   idle-red    — RunPod endpoints detected; not yet checked
 *   warming     — Wake-up in progress (flashing dot)
 *   green       — All RunPod endpoints responded OK
 *   red-failed  — One or more endpoints failed
 */

import { useState, useEffect } from 'react';
import { api } from '../api';
import './WakeUpButton.css';

export default function WakeUpButton({ councilModels }) {
  // Determine initial state from council composition
  const runpodModels = (councilModels ?? []).filter((m) =>
    m.base_url?.includes('proxy.runpod.net')
  );
  const hasRunPod = runpodModels.length > 0;

  const [status, setStatus] = useState(hasRunPod ? 'idle-red' : 'auto-green');
  const [results, setResults] = useState([]);

  // Re-evaluate if the council models prop changes (e.g. switching conversations)
  useEffect(() => {
    const rp = (councilModels ?? []).filter((m) =>
      m.base_url?.includes('proxy.runpod.net')
    );
    setStatus(rp.length > 0 ? 'idle-red' : 'auto-green');
    setResults([]);
  }, [councilModels]);

  const handleWakeUp = async () => {
    if (status === 'warming' || status === 'auto-green' || status === 'green') return;

    setStatus('warming');
    setResults([]);

    try {
      const allIds = (councilModels ?? []).map((m) => m.id);
      const data = await api.wakeup(allIds);

      if (data.status === 'no_runpod_endpoints') {
        // Shouldn't normally reach here (button hidden in this case) but handle gracefully
        setStatus('auto-green');
        return;
      }

      const resultList = data.results ?? [];
      setResults(resultList);

      const anyFailed = resultList.some((r) => !r.alive);
      setStatus(anyFailed ? 'red-failed' : 'green');
    } catch {
      setResults([]);
      setStatus('red-failed');
    }
  };

  // ── Derived label / tooltip ────────────────────────────────────────────────

  const label = {
    'auto-green': 'Models Awake',
    'idle-red': 'Wake Up Models',
    warming: 'Waking Up…',
    green: 'Models Awake',
    'red-failed': 'Wake Up Failed',
  }[status];

  const tooltip = buildTooltip(status, results, runpodModels);

  const clickable = status === 'idle-red' || status === 'red-failed';
  const stateClass = {
    'auto-green': 'state-green',
    'idle-red': 'state-red',
    warming: 'state-yellow',
    green: 'state-green',
    'red-failed': 'state-red',
  }[status];

  return (
    <div className="wakeup-wrapper">
      <button
        className={`wakeup-btn ${stateClass}`}
        onClick={clickable ? handleWakeUp : undefined}
        disabled={!clickable}
      >
        <span className="wakeup-dot" />
        {label}
      </button>
      <div className="wakeup-tooltip">{tooltip}</div>
    </div>
  );
}

function buildTooltip(status, results, runpodModels) {
  switch (status) {
    case 'auto-green':
      return 'No cold-start endpoints in this council — all models are always available.';

    case 'idle-red':
      return `This council has ${runpodModels.length} RunPod endpoint${
        runpodModels.length !== 1 ? 's' : ''
      } that may be cold. Click to wake them up before starting.`;

    case 'warming':
      return 'Contacting RunPod endpoints… this may take 10–30 seconds.';

    case 'green': {
      const names = results.map((r) => r.display_name).join(', ');
      return `All RunPod endpoints confirmed ready${names ? ': ' + names : ''}. Cloud models (OpenRouter) are always available.`;
    }

    case 'red-failed': {
      const failed = results.filter((r) => !r.alive);
      if (failed.length === 0) {
        return 'Wake-up request failed — check that the backend is running.';
      }
      const names = failed.map((r) => r.display_name).join(', ');
      return `${failed.length} endpoint${failed.length !== 1 ? 's' : ''} did not respond: ${names}. Click to try again.`;
    }

    default:
      return '';
  }
}
