/**
 * Settings panel — handles both first-run wizard mode and ongoing tabbed settings.
 *
 * Props:
 *   isOpen       {bool}     - Whether the panel is visible
 *   onClose      {function} - Called when panel should close
 *   onConfigSaved{function} - Called after any successful save (parent reloads config)
 *   forceWizard  {bool}     - Open in wizard mode regardless of pool state
 */

import { useState, useEffect } from 'react';
import { api } from '../api';
import './Settings.css';

// ── Helpers ────────────────────────────────────────────────────────────────

/**
 * Detect source type from base URL — matches the same logic used in backend/config.py.
 * Returns one of: 'RunPod' | 'OpenRouter' | 'Local' | 'Custom'
 */
export function getSourceBadge(baseUrl) {
  if (!baseUrl) return 'Custom';
  if (baseUrl.includes('proxy.runpod.net')) return 'RunPod';
  if (baseUrl.includes('openrouter.ai')) return 'OpenRouter';
  if (baseUrl.includes('localhost') || baseUrl.includes('127.0.0.1')) return 'Local';
  return 'Custom';
}

function generateId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older browsers
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

function emptyModel() {
  return { id: null, display_name: '', model: '', base_url: '', api_key: '' };
}

function emptyConfig() {
  return {
    available_models: [],
    chairman_id: '',
    summarization_model_id: '',
    favorites_council: [],
    history_raw_exchanges: 3,
    _warnings: [],
  };
}

// ── SourceBadge sub-component ──────────────────────────────────────────────

export function SourceBadge({ baseUrl }) {
  const label = getSourceBadge(baseUrl);
  return (
    <span className={`source-badge badge-${label.toLowerCase()}`}>{label}</span>
  );
}

// ── ModelForm sub-component ────────────────────────────────────────────────

/**
 * Reusable form for adding or editing a model.
 * Props:
 *   initial  {object}   - Starting values (use emptyModel() for new)
 *   onSave   {function} - Called with the saved model object
 *   onCancel {function} - Called when the user cancels
 */
function ModelForm({ initial, onSave, onCancel }) {
  const [form, setForm] = useState({ ...emptyModel(), ...initial });
  const [testStatus, setTestStatus] = useState(null);
  // testStatus: null | 'testing' | 'ok' | string (error message)

  const set = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    // Reset test status when connection-relevant fields change
    if (['base_url', 'api_key', 'model'].includes(field)) {
      setTestStatus(null);
    }
  };

  const handleTestConnection = async () => {
    setTestStatus('testing');
    try {
      await api.testConnection({
        model: form.model,
        base_url: form.base_url,
        api_key: form.api_key,
      });
      setTestStatus('ok');
    } catch (e) {
      setTestStatus(e.message || 'Connection failed');
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!isValid) return;
    onSave({ ...form, id: form.id || generateId() });
  };

  const isValid =
    form.display_name.trim() && form.model.trim() && form.base_url.trim();

  return (
    <form className="model-form" onSubmit={handleSubmit}>
      <div className="form-group">
        <label>Display Name</label>
        <input
          type="text"
          placeholder='e.g. GPT-4o (OpenRouter)'
          value={form.display_name}
          onChange={(e) => set('display_name', e.target.value)}
          autoFocus
        />
      </div>

      <div className="form-group">
        <label>
          Model ID
          <span className="field-hint">
            OpenRouter: <code>openai/gpt-4o</code> &nbsp;|&nbsp; Ollama / RunPod:{' '}
            <code>llama3.3:70b</code>
          </span>
        </label>
        <input
          type="text"
          placeholder='e.g. openai/gpt-4o or llama3.3:70b'
          value={form.model}
          onChange={(e) => set('model', e.target.value)}
        />
      </div>

      <div className="form-group">
        <label>Base URL</label>
        <input
          type="text"
          placeholder='e.g. https://openrouter.ai/api/v1'
          value={form.base_url}
          onChange={(e) => set('base_url', e.target.value)}
        />
        {form.base_url && (
          <div className="url-badge-preview">
            Detected source: <SourceBadge baseUrl={form.base_url} />
          </div>
        )}
      </div>

      <div className="form-group">
        <label>
          API Key
          <span className="field-optional">
            (leave blank for local Ollama / RunPod)
          </span>
        </label>
        <input
          type="password"
          placeholder='sk-...'
          value={form.api_key}
          onChange={(e) => set('api_key', e.target.value)}
        />
      </div>

      <div className="form-actions-row">
        <button
          type="button"
          className="btn-test-connection"
          onClick={handleTestConnection}
          disabled={!form.base_url.trim() || testStatus === 'testing'}
        >
          {testStatus === 'testing' ? 'Testing…' : 'Test Connection'}
        </button>
        {testStatus === 'ok' && (
          <span className="test-result test-ok">✓ Connected</span>
        )}
        {testStatus && testStatus !== 'ok' && testStatus !== 'testing' && (
          <span className="test-result test-fail">✗ {testStatus}</span>
        )}
      </div>

      <div className="form-footer">
        <button type="button" className="btn-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="btn-primary" disabled={!isValid}>
          Save Model
        </button>
      </div>
    </form>
  );
}

// ── Main Settings component ────────────────────────────────────────────────

export default function Settings({ isOpen, onClose, onConfigSaved, forceWizard }) {
  // 'loading' | 'wizard' | 'settings'
  const [mode, setMode] = useState('loading');
  const [config, setConfig] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  // Wizard-specific state
  const [wizardStep, setWizardStep] = useState(1);
  const [wizardModels, setWizardModels] = useState([]);
  const [wizardChairmanId, setWizardChairmanId] = useState('');
  const [wizardSumModelId, setWizardSumModelId] = useState('');
  const [showWizardAddForm, setShowWizardAddForm] = useState(false);
  const [wizardEditingId, setWizardEditingId] = useState(null);

  // Settings > Models tab state
  const [activeTab, setActiveTab] = useState('models');
  const [showModelForm, setShowModelForm] = useState(false);
  const [editingModel, setEditingModel] = useState(null);

  // Security tab state
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [passwordStatus, setPasswordStatus] = useState(null); // null | 'saving' | 'ok' | string (error)

  // Load config whenever panel opens
  useEffect(() => {
    if (isOpen) {
      loadConfig();
    }
  }, [isOpen]);

  // forceWizard overrides the detected mode
  useEffect(() => {
    if (forceWizard && isOpen && mode !== 'loading') {
      enterWizard();
    }
  }, [forceWizard, isOpen]);

  async function loadConfig() {
    setMode('loading');
    setSaveError(null);
    try {
      const cfg = await api.getConfig();
      setConfig(cfg);
      if (!cfg.available_models || cfg.available_models.length === 0 || forceWizard) {
        enterWizard();
      } else {
        setMode('settings');
      }
    } catch {
      // Backend unreachable or first run — start wizard with an empty slate
      setConfig(emptyConfig());
      enterWizard();
    }
  }

  function enterWizard() {
    setMode('wizard');
    setWizardStep(1);
    setWizardModels([]);
    setWizardChairmanId('');
    setWizardSumModelId('');
    setShowWizardAddForm(false);
    setWizardEditingId(null);
  }

  // ── Shared save helper ───────────────────────────────────────────────────

  async function callSaveConfig(configToSave) {
    setIsSaving(true);
    setSaveError(null);
    try {
      // Strip internal _-prefixed keys before sending — backend also strips them,
      // but keeping them out of the request is cleaner.
      const { _warnings, ...clean } = configToSave;
      await api.saveConfig(clean);
      if (onConfigSaved) onConfigSaved();
    } catch (e) {
      setSaveError(e.message || 'Failed to save. Is the backend running?');
      throw e;
    } finally {
      setIsSaving(false);
    }
  }

  // ── Wizard handlers ──────────────────────────────────────────────────────

  function wizardSaveModel(model) {
    setWizardModels((prev) => [...prev, model]);
    setShowWizardAddForm(false);
    // After first model in step 2, advance to step 3
    if (wizardStep === 2) setWizardStep(3);
  }

  function wizardUpdateModel(model) {
    setWizardModels((prev) => prev.map((m) => (m.id === model.id ? model : m)));
    setWizardEditingId(null);
  }

  function wizardDeleteModel(id) {
    setWizardModels((prev) => prev.filter((m) => m.id !== id));
    if (wizardChairmanId === id) setWizardChairmanId('');
    if (wizardSumModelId === id) setWizardSumModelId('');
  }

  async function finishLater() {
    // Save whatever has been entered so far, then close
    if (wizardModels.length > 0) {
      const partial = {
        available_models: wizardModels,
        chairman_id: wizardChairmanId || '',
        summarization_model_id: wizardSumModelId || '',
        favorites_council: [],
        history_raw_exchanges: config?.history_raw_exchanges ?? 3,
      };
      try {
        await callSaveConfig(partial);
      } catch {
        // Close even if save failed — user can fix it later
      }
    }
    onClose();
  }

  async function finishWizard() {
    const finalConfig = {
      available_models: wizardModels,
      chairman_id: wizardChairmanId || '',
      summarization_model_id: wizardSumModelId || '',
      favorites_council: [],
      history_raw_exchanges: config?.history_raw_exchanges ?? 3,
    };
    try {
      await callSaveConfig(finalConfig);
      onClose();
    } catch {
      // saveError state is set by callSaveConfig — user sees the message
    }
  }

  // ── Settings tab handlers ────────────────────────────────────────────────

  function settingsAddModel(model) {
    setConfig((prev) => ({
      ...prev,
      available_models: [...prev.available_models, model],
    }));
    setShowModelForm(false);
    setEditingModel(null);
  }

  function settingsEditModel(model) {
    setConfig((prev) => ({
      ...prev,
      available_models: prev.available_models.map((m) =>
        m.id === model.id ? model : m
      ),
    }));
    setShowModelForm(false);
    setEditingModel(null);
  }

  function settingsDeleteModel(id) {
    setConfig((prev) => ({
      ...prev,
      available_models: prev.available_models.filter((m) => m.id !== id),
      chairman_id: prev.chairman_id === id ? '' : prev.chairman_id,
      summarization_model_id:
        prev.summarization_model_id === id ? '' : prev.summarization_model_id,
      favorites_council: (prev.favorites_council || []).filter((fid) => fid !== id),
    }));
  }

  async function handleSaveSettings() {
    try {
      await callSaveConfig(config);
    } catch {
      // Error shown in footer via saveError
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────

  if (!isOpen) return null;

  return (
    <div
      className="settings-overlay"
      // Clicking the dark backdrop closes the panel
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="settings-panel">
        {mode === 'loading' && (
          <div className="settings-loading">Loading settings…</div>
        )}
        {mode === 'wizard' && renderWizard()}
        {mode === 'settings' && renderSettings()}
      </div>
    </div>
  );

  // ── Wizard rendering ─────────────────────────────────────────────────────

  function renderWizard() {
    return (
      <div className="wizard">
        <div className="wizard-header">
          <div className="wizard-steps">
            {[1, 2, 3, 4, 5, 6].map((n) => (
              <div
                key={n}
                className={[
                  'wizard-step-dot',
                  wizardStep > n ? 'done' : '',
                  wizardStep === n ? 'active' : '',
                ]
                  .join(' ')
                  .trim()}
              />
            ))}
          </div>
          <button className="btn-finish-later" onClick={finishLater}>
            Finish Later
          </button>
        </div>

        <div className="wizard-body">
          {wizardStep === 1 && renderWizardStep1()}
          {wizardStep === 2 && renderWizardStep2()}
          {wizardStep === 3 && renderWizardStep3()}
          {wizardStep === 4 && renderWizardStep4()}
          {wizardStep === 5 && renderWizardStep5()}
          {wizardStep === 6 && renderWizardStep6()}
        </div>
      </div>
    );
  }

  function renderWizardStep1() {
    return (
      <div className="wizard-step">
        <div className="wizard-icon">🤝</div>
        <h2>Welcome to LLM Council</h2>
        <p>
          LLM Council lets multiple AI models debate your questions and then
          synthesizes their answers into a single response.
        </p>
        <p className="wizard-tip">
          You can use <strong>OpenRouter</strong> for cloud models,{' '}
          <strong>RunPod</strong> for open-weight models, or{' '}
          <strong>local Ollama</strong> — or any mix. You&apos;ll need API keys
          for whichever services you use.
        </p>
        <button
          className="btn-primary btn-large"
          onClick={() => setWizardStep(2)}
        >
          Get Started →
        </button>
      </div>
    );
  }

  function renderWizardStep2() {
    return (
      <div className="wizard-step">
        <h2>Add Your First Model</h2>
        <p>
          Fill in the details for your first model. You&apos;ll add more in the
          next step.
        </p>
        <ModelForm
          initial={emptyModel()}
          onSave={wizardSaveModel}
          onCancel={() => setWizardStep(1)}
        />
      </div>
    );
  }

  function renderWizardStep3() {
    return (
      <div className="wizard-step">
        <h2>Add More Models</h2>
        <p>
          You need at least 2 models for the council to work. Add as many as
          you like.
        </p>

        <div className="wizard-model-list">
          {wizardModels.map((m) =>
            wizardEditingId === m.id ? (
              <div key={m.id} className="wizard-model-edit">
                <ModelForm
                  initial={m}
                  onSave={wizardUpdateModel}
                  onCancel={() => setWizardEditingId(null)}
                />
              </div>
            ) : (
              <div key={m.id} className="wizard-model-item">
                <SourceBadge baseUrl={m.base_url} />
                <span className="model-display-name">{m.display_name}</span>
                <span className="model-id-small">{m.model}</span>
                <div className="model-item-actions">
                  <button
                    className="btn-icon"
                    onClick={() => setWizardEditingId(m.id)}
                  >
                    Edit
                  </button>
                  <button
                    className="btn-icon btn-icon-danger"
                    onClick={() => wizardDeleteModel(m.id)}
                  >
                    Remove
                  </button>
                </div>
              </div>
            )
          )}
        </div>

        {showWizardAddForm ? (
          <ModelForm
            initial={emptyModel()}
            onSave={(m) => {
              setWizardModels((prev) => [...prev, m]);
              setShowWizardAddForm(false);
            }}
            onCancel={() => setShowWizardAddForm(false)}
          />
        ) : (
          <button
            className="btn-secondary btn-add-another"
            onClick={() => setShowWizardAddForm(true)}
          >
            + Add Another Model
          </button>
        )}

        <div className="wizard-nav">
          <button
            className="btn-primary"
            onClick={() => setWizardStep(4)}
            disabled={wizardModels.length < 1}
          >
            {wizardModels.length < 2
              ? `Continue with ${wizardModels.length} model (need 2+ for the council)`
              : "I'm done adding models →"}
          </button>
        </div>
      </div>
    );
  }

  function renderWizardStep4() {
    return (
      <div className="wizard-step">
        <h2>Choose a Chairman</h2>
        <p>
          The Chairman reads all debate responses and writes the final
          synthesized answer. Pick your most capable model for this role.
        </p>
        <div className="form-group">
          <label>Chairman Model</label>
          <select
            value={wizardChairmanId}
            onChange={(e) => setWizardChairmanId(e.target.value)}
          >
            <option value="">— Select a model —</option>
            {wizardModels.map((m) => (
              <option key={m.id} value={m.id}>
                {m.display_name}
              </option>
            ))}
          </select>
        </div>
        <div className="wizard-nav">
          <button className="btn-secondary" onClick={() => setWizardStep(3)}>
            ← Back
          </button>
          <button
            className="btn-primary"
            onClick={() => setWizardStep(5)}
            disabled={!wizardChairmanId}
          >
            Next →
          </button>
        </div>
      </div>
    );
  }

  function renderWizardStep5() {
    return (
      <div className="wizard-step">
        <h2>Choose a Summarization Model</h2>
        <p>
          This model compresses older conversation history in the background so
          the council stays focused. It doesn&apos;t need to be in your council
          — any capable model works well here.
        </p>
        <div className="form-group">
          <label>Summarization Model</label>
          <select
            value={wizardSumModelId}
            onChange={(e) => setWizardSumModelId(e.target.value)}
          >
            <option value="">— Select a model —</option>
            {wizardModels.map((m) => (
              <option key={m.id} value={m.id}>
                {m.display_name}
              </option>
            ))}
          </select>
        </div>
        <div className="wizard-nav">
          <button className="btn-secondary" onClick={() => setWizardStep(4)}>
            ← Back
          </button>
          <button
            className="btn-primary"
            onClick={() => setWizardStep(6)}
            disabled={!wizardSumModelId}
          >
            Next →
          </button>
        </div>
      </div>
    );
  }

  function renderWizardStep6() {
    const chairmanModel = wizardModels.find((m) => m.id === wizardChairmanId);
    const sumModel = wizardModels.find((m) => m.id === wizardSumModelId);
    return (
      <div className="wizard-step wizard-done">
        <div className="wizard-icon">🎉</div>
        <h2>You&apos;re all set!</h2>
        <p>
          You&apos;ve added{' '}
          <strong>
            {wizardModels.length} model{wizardModels.length !== 1 ? 's' : ''}
          </strong>{' '}
          to your pool.
        </p>
        <ul className="wizard-summary">
          <li>
            Chairman:{' '}
            <strong>{chairmanModel?.display_name ?? '—'}</strong>
          </li>
          <li>
            Summarization:{' '}
            <strong>{sumModel?.display_name ?? '—'}</strong>
          </li>
        </ul>
        <p>
          You can change all of these settings any time using the ⚙ gear icon.
        </p>
        <button
          className="btn-primary btn-large"
          onClick={finishWizard}
          disabled={isSaving}
        >
          {isSaving ? 'Saving…' : 'Start Using LLM Council →'}
        </button>
        {saveError && <div className="save-error" style={{ marginTop: 12 }}>{saveError}</div>}
      </div>
    );
  }

  // ── Ongoing settings rendering ───────────────────────────────────────────

  function renderSettings() {
    return (
      <div className="settings-content">
        <div className="settings-header">
          <h2>Settings</h2>
          <button className="btn-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="settings-tabs">
          {['models', 'defaults', 'history', 'security'].map((tab) => (
            <button
              key={tab}
              className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        <div className="settings-tab-content">
          {activeTab === 'models' && renderModelsTab()}
          {activeTab === 'defaults' && renderDefaultsTab()}
          {activeTab === 'history' && renderHistoryTab()}
          {activeTab === 'security' && renderSecurityTab()}
        </div>

        <div className="settings-footer">
          {saveError && (
            <span className="save-error">{saveError}</span>
          )}
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn-primary"
            onClick={handleSaveSettings}
            disabled={isSaving}
          >
            {isSaving ? 'Saving…' : 'Save Settings'}
          </button>
        </div>
      </div>
    );
  }

  function renderModelsTab() {
    const models = config?.available_models ?? [];
    return (
      <div className="models-tab">
        <div className="tab-info-bar">
          <span className="tab-info-text">
            ℹ Changes only apply to new conversations. Existing conversations
            keep their original model settings.
          </span>
          <button
            className="btn-primary btn-sm"
            onClick={() => {
              setEditingModel(null);
              setShowModelForm(true);
            }}
          >
            + Add Model
          </button>
        </div>

        {models.length === 0 && !showModelForm && (
          <div className="empty-pool">
            <p>No models in your pool yet.</p>
            <p>
              Click <strong>+ Add Model</strong> to get started.
            </p>
          </div>
        )}

        {showModelForm && (
          <div className="model-form-wrapper">
            <h3>{editingModel ? 'Edit Model' : 'Add Model'}</h3>
            <ModelForm
              initial={editingModel ?? emptyModel()}
              onSave={editingModel ? settingsEditModel : settingsAddModel}
              onCancel={() => {
                setShowModelForm(false);
                setEditingModel(null);
              }}
            />
          </div>
        )}

        {!showModelForm &&
          models.map((m) => (
            <div key={m.id} className="model-list-item">
              <div className="model-list-info">
                <SourceBadge baseUrl={m.base_url} />
                <span className="model-list-name">{m.display_name}</span>
                <span className="model-list-id">{m.model}</span>
              </div>
              <div className="model-list-actions">
                <button
                  className="btn-icon"
                  onClick={() => {
                    setEditingModel(m);
                    setShowModelForm(true);
                  }}
                >
                  Edit
                </button>
                <button
                  className="btn-icon btn-icon-danger"
                  onClick={() => settingsDeleteModel(m.id)}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
      </div>
    );
  }

  function renderDefaultsTab() {
    const models = config?.available_models ?? [];
    return (
      <div className="defaults-tab">
        <div className="form-group">
          <label>Chairman Model</label>
          <p className="field-help">
            Reads all debate responses and writes the final answer. Pick your
            most capable model.
          </p>
          <select
            value={config?.chairman_id ?? ''}
            onChange={(e) =>
              setConfig((prev) => ({ ...prev, chairman_id: e.target.value }))
            }
          >
            <option value="">— Select a model —</option>
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.display_name}
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>Favorites Council</label>
          <p className="field-help">
            These models will be pre-selected whenever you start a new
            conversation. You can always change the selection before starting.
          </p>
          {models.length === 0 ? (
            <p className="no-models-hint">Add models in the Models tab first.</p>
          ) : (
            <div className="favorites-list">
              {models.map((m) => {
                const favs = config?.favorites_council ?? [];
                return (
                  <label key={m.id} className="favorites-item">
                    <input
                      type="checkbox"
                      checked={favs.includes(m.id)}
                      onChange={(e) => {
                        const updated = e.target.checked
                          ? [...favs, m.id]
                          : favs.filter((id) => id !== m.id);
                        setConfig((prev) => ({
                          ...prev,
                          favorites_council: updated,
                        }));
                      }}
                    />
                    <SourceBadge baseUrl={m.base_url} />
                    <span>{m.display_name}</span>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      </div>
    );
  }

  function renderHistoryTab() {
    const models = config?.available_models ?? [];
    const rawExchanges = config?.history_raw_exchanges ?? 3;
    const noSumModel = !config?.summarization_model_id;

    return (
      <div className="history-tab">
        {noSumModel && (
          <div className="warning-banner">
            ⚠ No summarization model selected — new conversations are blocked
            until one is chosen below.
          </div>
        )}

        <div className="form-group">
          <label>Recent Exchanges Sent in Full Detail</label>
          <p className="field-help">
            How many recent conversation turns (question + answer pairs) are
            sent to models verbatim. Older turns are compressed into a running
            summary. Range: 1–10.
          </p>
          <div className="slider-row">
            <input
              type="range"
              min="1"
              max="10"
              value={rawExchanges}
              onChange={(e) =>
                setConfig((prev) => ({
                  ...prev,
                  history_raw_exchanges: parseInt(e.target.value, 10),
                }))
              }
            />
            <span className="slider-value">{rawExchanges}</span>
          </div>
        </div>

        <div className="form-group">
          <label>Summarization Model</label>
          <p className="field-help">
            Compresses older conversation history in the background. It can be
            any model in your pool — it doesn&apos;t need to be part of the
            council.
          </p>
          <select
            value={config?.summarization_model_id ?? ''}
            onChange={(e) =>
              setConfig((prev) => ({
                ...prev,
                summarization_model_id: e.target.value,
              }))
            }
          >
            <option value="">— Select a model —</option>
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.display_name}
              </option>
            ))}
          </select>
        </div>
      </div>
    );
  }

  function renderSecurityTab() {
    const handleChangePassword = async (e) => {
      e.preventDefault();
      setPasswordStatus(null);

      if (newPassword.length < 4) {
        setPasswordStatus('New password must be at least 4 characters.');
        return;
      }
      if (newPassword !== confirmNewPassword) {
        setPasswordStatus('New passwords do not match.');
        return;
      }

      setPasswordStatus('saving');
      try {
        const result = await api.changePassword(oldPassword, newPassword);
        // Update the stored token with the new one
        if (result.token) {
          sessionStorage.setItem('council_token', result.token);
        }
        setPasswordStatus('ok');
        setOldPassword('');
        setNewPassword('');
        setConfirmNewPassword('');
      } catch (err) {
        setPasswordStatus(err.message || 'Password change failed.');
      }
    };

    return (
      <div className="security-tab">
        <h3>Change Password</h3>
        <p className="field-help">
          Your password protects this instance from unauthorized access and
          encrypts your stored API keys. If you change it, all API keys will be
          re-encrypted with the new password.
        </p>

        <form onSubmit={handleChangePassword} className="password-change-form">
          <div className="form-group">
            <label>Current Password</label>
            <input
              type="password"
              value={oldPassword}
              onChange={(e) => {
                setOldPassword(e.target.value);
                setPasswordStatus(null);
              }}
            />
          </div>
          <div className="form-group">
            <label>New Password</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => {
                setNewPassword(e.target.value);
                setPasswordStatus(null);
              }}
            />
          </div>
          <div className="form-group">
            <label>Confirm New Password</label>
            <input
              type="password"
              value={confirmNewPassword}
              onChange={(e) => {
                setConfirmNewPassword(e.target.value);
                setPasswordStatus(null);
              }}
            />
          </div>

          {passwordStatus === 'ok' && (
            <div className="password-success">Password changed successfully.</div>
          )}
          {passwordStatus && passwordStatus !== 'ok' && passwordStatus !== 'saving' && (
            <div className="password-error">{passwordStatus}</div>
          )}

          <button
            type="submit"
            className="btn-primary"
            disabled={!oldPassword || !newPassword || passwordStatus === 'saving'}
          >
            {passwordStatus === 'saving' ? 'Changing...' : 'Change Password'}
          </button>
        </form>
      </div>
    );
  }
}
