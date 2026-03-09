/**
 * SummarizationPicker — Screen 3 of the 3-screen new conversation flow.
 *
 * Single-select picker for choosing the Summarization model for this
 * conversation. Defaults to the current summarization model from Settings.
 * Includes a "Use Default" button to skip quickly.
 *
 * Props:
 *   models          {array}    - Available models from the council config
 *   defaultId       {string}   - Default summarization model ID from Settings
 *   onSelect        {function} - Called with selected summarization model ID
 *   onBack          {function} - Go back to chairman picker
 *   onCancel        {function} - Cancel the entire flow
 *   isCreating      {bool}     - True while the create-conversation API call is in flight
 */

import { useState } from 'react';
import { SourceBadge } from './Settings';
import { stripProviderPrefix } from '../utils/costEstimate';
import './CouncilPicker.css';

export default function SummarizationPicker({
  models,
  defaultId,
  onSelect,
  onBack,
  onCancel,
  isCreating,
}) {
  const [selectedId, setSelectedId] = useState(defaultId || '');

  const handleStart = () => {
    if (!selectedId || isCreating) return;
    onSelect(selectedId);
  };

  const handleUseDefault = () => {
    if (defaultId && !isCreating) {
      onSelect(defaultId);
    }
  };

  return (
    <div className="council-picker">
      <div className="council-picker-inner">
        <h2>Choose Your Summarization Model</h2>
        <p className="council-picker-subtitle">
          The summarization model compresses older conversation history into a
          running summary. This keeps long conversations efficient without
          losing context.
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
                  name="summarization"
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
            <button
              className="btn-secondary"
              onClick={handleUseDefault}
              disabled={isCreating}
            >
              Use Default
            </button>
          )}
          <button
            className="btn-primary"
            onClick={handleStart}
            disabled={!selectedId || isCreating}
          >
            {isCreating ? 'Starting…' : 'Start Conversation'}
          </button>
        </div>
      </div>
    </div>
  );
}
