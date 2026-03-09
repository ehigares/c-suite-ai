import { useState, useEffect, useRef, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import WakeUpButton from './WakeUpButton';
import { SourceBadge } from './Settings';
import { calculateApiCalls, estimateInputTokens, formatCostHint, stripProviderPrefix } from '../utils/costEstimate';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  warnings,
}) {
  const [input, setInput] = useState('');
  const [debouncedTokens, setDebouncedTokens] = useState(0);
  const debounceRef = useRef(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  // Debounced token estimate — updates 300ms after user stops typing
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedTokens(input.trim() ? estimateInputTokens(input) : 0);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [input]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // ── Council header data ────────────────────────────────────────────────────
  //
  // Memoised on conversation.id so the array reference is stable across the
  // many setCurrentConversation() calls that happen during SSE streaming.
  // Without this, WakeUpButton's useEffect fires on every streamed chunk and
  // resets the button state from green back to idle-red mid-conversation.
  //
  // IMPORTANT: This hook MUST be declared before any conditional returns
  // to avoid React's "Rendered more hooks than during the previous render" error.

  const councilModels = useMemo(
    () => conversation?.council_config?.available_models ?? [],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [conversation?.id]
  );
  const chairmanId = conversation?.council_config?.chairman_id ?? '';

  // ── No conversation selected ───────────────────────────────────────────────

  if (!conversation) {
    return (
      <div className="chat-interface">
        {warnings && warnings.length > 0 && (
          <div className="warning-banners">
            {warnings.map((w, i) => (
              <div key={i} className="warning-banner-item">{w}</div>
            ))}
          </div>
        )}
        <div className="empty-state">
          <h2>Welcome to C-Suite AI</h2>
          <p>Create a new conversation to get started</p>
        </div>
      </div>
    );
  }

  // ── Active conversation ────────────────────────────────────────────────────

  return (
    <div className="chat-interface">
      {/* Global config warning banners */}
      {warnings && warnings.length > 0 && (
        <div className="warning-banners">
          {warnings.map((w, i) => (
            <div key={i} className="warning-banner-item">{w}</div>
          ))}
        </div>
      )}

      {/* Council header — model badges + wake-up button */}
      {councilModels.length > 0 && (
        <div className="council-header">
          <div className="council-model-badges">
            {councilModels.map((m) => (
              <span key={m.id} className="council-model-badge">
                <SourceBadge baseUrl={m.base_url} />
                <span className="council-model-badge-name">{stripProviderPrefix(m.display_name)}</span>
                {m.id === chairmanId && (
                  <span className="council-chairman-crown" title="Chairman">👑</span>
                )}
              </span>
            ))}
          </div>
          <WakeUpButton councilModels={councilModels} />
        </div>
      )}

      {/* Cost hint — subtle line below council header */}
      {councilModels.length > 0 && (
        <div className="cost-hint">
          {formatCostHint(calculateApiCalls(councilModels.length), debouncedTokens)}
        </div>
      )}

      {/* Messages */}
      <div className="messages-container">
        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>Start a conversation</h2>
            <p>Ask a question to consult the C-Suite</p>
          </div>
        ) : (
          conversation.messages.map((msg, index) => (
            <div key={index} className="message-group">
              {msg.role === 'user' ? (
                <div className="user-message">
                  <div className="message-label">You</div>
                  <div className="message-content">
                    <div className="markdown-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="assistant-message">
                  <div className="message-label">C-Suite AI</div>

                  {/* Stage 1 */}
                  {msg.loading?.stage1 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 1: Collecting individual responses...</span>
                    </div>
                  )}
                  {msg.stage1 && <Stage1 responses={msg.stage1} />}

                  {/* Stage 2 */}
                  {msg.loading?.stage2 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 2: Peer rankings...</span>
                    </div>
                  )}
                  {msg.stage2 && (
                    <Stage2
                      rankings={msg.stage2}
                      labelToModel={msg.metadata?.label_to_model}
                      aggregateRankings={msg.metadata?.aggregate_rankings}
                    />
                  )}

                  {/* Stage 3 */}
                  {msg.loading?.stage3 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 3: Final synthesis...</span>
                    </div>
                  )}
                  {msg.stage3 && <Stage3 finalResponse={msg.stage3} />}
                </div>
              )}
            </div>
          ))
        )}

        {isLoading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>Consulting the council...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Message input — always visible for multi-turn conversations */}
      <form className="input-form" onSubmit={handleSubmit}>
        <textarea
          className="message-input"
          placeholder="Ask your question… (Shift+Enter for new line, Enter to send)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          rows={3}
        />
        <button
          type="submit"
          className="send-button"
          disabled={!input.trim() || isLoading}
        >
          Send
        </button>
      </form>
    </div>
  );
}
