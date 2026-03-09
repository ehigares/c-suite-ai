/**
 * ChairmanPicker — Screen 2 of the 3-screen new conversation flow.
 *
 * Single-select picker for choosing the Chairman model for this conversation.
 * Defaults to the current chairman from Settings. Includes a "Use Default"
 * button to skip quickly.
 *
 * Props:
 *   models          {array}    - Available models from the council config
 *   defaultId       {string}   - Default chairman ID from Settings
 *   onSelect        {function} - Called with selected chairman ID
 *   onBack          {function} - Go back to council picker
 *   onCancel        {function} - Cancel the entire flow
 */

import { useState } from 'react';
import { SourceBadge } from './Settings';
import { stripProviderPrefix } from '../utils/costEstimate';
import './CouncilPicker.css';

export default function ChairmanPicker({
  models,
  defaultId,
  onSelect,
  onBack,
  onCancel,
}) {
  const [selectedId, setSelectedId] = useState(defaultId || '');

  const handleContinue = () => {
    if (!selectedId) return;
    onSelect(selectedId);
  };

  const handleUseDefault = () => {
    if (defaultId) {
      onSelect(defaultId);
    }
  };

  return (
    <div className="council-picker">
      <div className="council-picker-inner">
        <h2>Choose Your Chairman</h2>
        <p className="council-picker-subtitle">
          The Chairman reads all responses and rankings, then writes the final
          synthesized answer. Pick one model for this role.
        </p>

        {/* Model list — single select */}
        <div className="picker-model-list">
          {models.map((m) => {
            const isSelected = m.id === selectedId;
            return (
              <div
                key={m.id}
                className={`picker-model-item ${isSelected ? 'selected' : ''}`}
                onClick={() => setSelectedId(m.id)}
              >
                <input
                  type="radio"
                  name="chairman"
                  checked={isSelected}
                  onChange={() => setSelectedId(m.id)}
                  onClick={(e) => e.stopPropagation()}
                />
                <div className="picker-model-info">
                  <SourceBadge baseUrl={m.base_url} />
                  <span className="picker-model-name">{stripProviderPrefix(m.display_name)}</span>
                  <span className="picker-model-id">{m.model}</span>
                  {m.id === defaultId && (
                    <span className="chairman-badge">Default</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="picker-footer">
          <button className="btn-secondary" onClick={onBack}>
            Back
          </button>
          <button className="btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          {defaultId && (
            <button className="btn-secondary" onClick={handleUseDefault}>
              Use Default
            </button>
          )}
          <button
            className="btn-primary"
            onClick={handleContinue}
            disabled={!selectedId}
          >
            Continue
          </button>
        </div>
      </div>
    </div>
  );
}
