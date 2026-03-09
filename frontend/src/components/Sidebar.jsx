import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onOpenSettings,
  onOpenWizard,
  isNewConversationBlocked,
  blockReason,
}) {
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-title-row">
          <h1>C-Suite AI</h1>
          <button
            className="gear-btn"
            onClick={onOpenSettings}
            title="Open Settings"
          >
            ⚙
          </button>
        </div>

        <div
          className={`new-conversation-btn-wrapper ${isNewConversationBlocked ? 'blocked' : ''}`}
          title={isNewConversationBlocked ? blockReason : undefined}
        >
          <button
            className="new-conversation-btn"
            onClick={isNewConversationBlocked ? undefined : onNewConversation}
            disabled={isNewConversationBlocked}
          >
            + New Conversation
          </button>
        </div>
      </div>

      <div className="sidebar-wizard-row">
        <button className="setup-wizard-btn" onClick={onOpenWizard}>
          ⚙ Setup Wizard
        </button>
      </div>

      <div className="conversation-list">
        {conversations.length === 0 ? (
          <div className="no-conversations">No conversations yet</div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${
                conv.id === currentConversationId ? 'active' : ''
              }`}
              onClick={() => onSelectConversation(conv.id)}
            >
              <div className="conversation-title">
                {conv.title || 'New Conversation'}
              </div>
              <div className="conversation-meta">
                {conv.message_count} messages
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
