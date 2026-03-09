/**
 * CouncilPicker — shown instead of ChatInterface when "New Conversation" is clicked.
 *
 * The user selects which models from their pool will participate in this conversation.
 * The selection is locked for the duration of the conversation once "Start" is clicked.
 *
 * Props:
 *   config       {object}   - Full council config (available_models, chairman_id, favorites_council)
 *   onStart      {function} - Called with selected model ID array when user starts conversation
 *   onCancel     {function} - Called when user cancels (returns to previous view)
 *   onOpenWizard {function} - Opens the setup wizard (shown when pool is empty)
 *   isCreating   {bool}     - True while the create-conversation API call is in flight
 */

import { useState, useMemo } from 'react';
import { SourceBadge } from './Settings';
import './CouncilPicker.css';

export default function CouncilPicker({
  config,
  onStart,
  onCancel,
  onOpenWizard,
  isCreating,
}) {
  const models = config?.available_models ?? [];
  const chairmanId = config?.chairman_id ?? '';
  const favorites = config?.favorites_council ?? [];

  // Initialise selection from Favorites Council (or empty if no favorites set)
  const [selectedIds, setSelectedIds] = useState(() => new Set(favorites));

  const selectedCount = selectedIds.size;

  // ── Selection helpers ──────────────────────────────────────────────────────

  const toggleModel = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const allSelected = models.length > 0 && selectedIds.size === models.length;

  const toggleAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(models.map((m) => m.id)));
    }
  };

  // ── Warnings (computed from selected models only) ──────────────────────────

  const warnings = useMemo(() => {
    const selected = models.filter((m) => selectedIds.has(m.id));
    const w = [];

    if (selectedCount === 2) {
      w.push({
        type: 'yellow',
        text: 'Only 2 models selected — the council debate will have limited diversity.',
      });
    }

    if (selectedCount >= 7) {
      w.push({
        type: 'yellow',
        text: 'Large council — expect higher cost and slower responses than usual.',
      });
    }

    const hasFreeModels = selected.some((m) => m.model?.includes(':free'));
    if (hasFreeModels) {
      w.push({
        type: 'blue',
        text: 'One or more free OpenRouter models are selected. Free models have a 200 requests/day limit.',
      });
    }

    const hasRunPod = selected.some((m) =>
      m.base_url?.includes('proxy.runpod.net')
    );
    if (hasRunPod) {
      w.push({
        type: 'blue',
        text: 'RunPod models may be cold-starting. Use the Wake Up button after starting the conversation to check.',
      });
    }

    return w;
  }, [selectedIds, models, selectedCount]);

  // ── Empty pool state ───────────────────────────────────────────────────────

  if (models.length === 0) {
    return (
      <div className="council-picker">
        <div className="council-picker-inner">
          <h2>No Models Yet</h2>
          <div className="picker-empty-state">
            <p>You haven&apos;t added any models to your pool.</p>
            <p>Use the Setup Wizard to add your first model.</p>
            <button className="btn-primary" onClick={onOpenWizard}>
              Launch Setup Wizard
            </button>
          </div>
          <div className="picker-footer" style={{ marginTop: 24 }}>
            <button className="btn-secondary" onClick={onCancel}>
              Cancel
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Normal picker ──────────────────────────────────────────────────────────

  const handleStart = () => {
    if (selectedCount < 2 || isCreating) return;
    onStart(Array.from(selectedIds));
  };

  return (
    <div className="council-picker">
      <div className="council-picker-inner">
        <h2>Choose Your Council</h2>
        <p className="council-picker-subtitle">
          Select which models will debate this conversation. Your Favorites Council is
          pre-selected — you can change the selection before starting.
        </p>

        {/* Selection summary */}
        <div className="picker-selection-bar">
          <span className="picker-selection-count">
            {selectedCount} of {models.length} model{models.length !== 1 ? 's' : ''} selected
          </span>
          <button className="picker-select-all-btn" onClick={toggleAll}>
            {allSelected ? 'Deselect all' : 'Select all'}
          </button>
        </div>

        {/* Model list */}
        <div className="picker-model-list">
          {models.map((m) => {
            const isSelected = selectedIds.has(m.id);
            const isChairman = m.id === chairmanId;
            return (
              <div
                key={m.id}
                className={`picker-model-item ${isSelected ? 'selected' : ''}`}
                onClick={() => toggleModel(m.id)}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => toggleModel(m.id)}
                  onClick={(e) => e.stopPropagation()}
                />
                <div className="picker-model-info">
                  <SourceBadge baseUrl={m.base_url} />
                  <span className="picker-model-name">{m.display_name}</span>
                  <span className="picker-model-id">{m.model}</span>
                  {isChairman && (
                    <span className="chairman-badge">Chairman</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Inline warnings for current selection */}
        {warnings.length > 0 && (
          <div className="picker-warnings">
            {warnings.map((w, i) => (
              <div
                key={i}
                className={`picker-warning picker-warning-${w.type}`}
              >
                {w.type === 'yellow' ? '⚠' : 'ℹ'} {w.text}
              </div>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="picker-footer">
          <button className="btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button
            className="btn-primary"
            onClick={handleStart}
            disabled={selectedCount < 2 || isCreating}
            title={
              selectedCount < 2
                ? 'Select at least 2 models to start a conversation'
                : undefined
            }
          >
            {isCreating
              ? 'Starting…'
              : selectedCount < 2
              ? `Select ${2 - selectedCount} more`
              : 'Start Conversation'}
          </button>
        </div>
      </div>
    </div>
  );
}
