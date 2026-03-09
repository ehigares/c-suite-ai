import { useState, useEffect, useMemo, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import CouncilPicker from './components/CouncilPicker';
import Settings from './components/Settings';
import LoginScreen from './components/LoginScreen';
import { api, setOnAuthExpired, setToken, clearToken } from './api';
import './App.css';

function App() {
  // Auth state — null means "checking", true/false means resolved
  const [isAuthenticated, setIsAuthenticated] = useState(null);

  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  // Settings panel
  const [showSettings, setShowSettings] = useState(false);
  const [forceWizard, setForceWizard] = useState(false);

  // Council picker — shown instead of ChatInterface when starting a new conversation
  const [showPicker, setShowPicker] = useState(false);
  const [isCreatingConversation, setIsCreatingConversation] = useState(false);

  // Global council config — drives warnings and CouncilPicker model list
  const [councilConfig, setCouncilConfig] = useState(null);

  // Register the auth-expired callback so api.js can trigger a logout
  const handleAuthExpired = useCallback(() => {
    setIsAuthenticated(false);
  }, []);

  useEffect(() => {
    setOnAuthExpired(handleAuthExpired);
  }, [handleAuthExpired]);

  // On mount, check if we have a valid token
  useEffect(() => {
    const token = sessionStorage.getItem('council_token');
    if (token) {
      // Try a lightweight authenticated call to verify the token is still valid
      api.getConfig()
        .then((cfg) => {
          setCouncilConfig(cfg);
          setIsAuthenticated(true);
        })
        .catch(() => {
          // Token is expired or invalid
          clearToken();
          setIsAuthenticated(false);
        });
    } else {
      // Check if password is even set — if not, show setup
      api.getAuthStatus()
        .then((status) => {
          if (!status.password_set) {
            // No password yet — show login/setup screen
            setIsAuthenticated(false);
          } else {
            setIsAuthenticated(false);
          }
        })
        .catch(() => {
          setIsAuthenticated(false);
        });
    }
  }, []);

  // After authentication, load data
  useEffect(() => {
    if (isAuthenticated) {
      loadConversations();
      loadCouncilConfig();
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (currentConversationId && isAuthenticated) {
      loadConversation(currentConversationId);
    }
  }, [currentConversationId, isAuthenticated]);

  const handleAuthenticated = (token) => {
    setToken(token);
    setIsAuthenticated(true);
  };

  const loadConversations = async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const loadConversation = async (id) => {
    try {
      const conv = await api.getConversation(id);
      setCurrentConversation(conv);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const loadCouncilConfig = async () => {
    try {
      const cfg = await api.getConfig();
      setCouncilConfig(cfg);
    } catch {
      // Backend not running yet — no warnings shown
    }
  };

  // ── Warning / blocking logic ─────────────────────────────────────────────

  const blockingWarnings = useMemo(() => {
    if (!councilConfig) return [];
    const warnings = [];

    if (councilConfig._warnings?.includes('chairman_orphaned')) {
      warnings.push(
        '⚠ Your Chairman model has been removed from the pool. Please reassign one in Settings → Defaults.'
      );
    }
    if (councilConfig._warnings?.includes('summarization_orphaned')) {
      warnings.push(
        '⚠ Your Summarization model has been removed from the pool. Please reassign one in Settings → History.'
      );
    }

    const hasModels = (councilConfig.available_models?.length ?? 0) > 0;
    if (hasModels && !councilConfig.summarization_model_id) {
      warnings.push(
        '⚠ No summarization model selected — new conversations are blocked. Go to Settings → History to fix this.'
      );
    }

    return warnings;
  }, [councilConfig]);

  const isNewConversationBlocked = blockingWarnings.length > 0;
  const blockReason = isNewConversationBlocked
    ? 'Fix the warnings shown in the chat area before starting a new conversation.'
    : undefined;

  // ── Settings handlers ───────────────────────────────────────────────────

  const handleOpenSettings = () => {
    setForceWizard(false);
    setShowSettings(true);
  };

  const handleOpenWizard = () => {
    setForceWizard(true);
    setShowSettings(true);
  };

  const handleCloseSettings = () => {
    setShowSettings(false);
    setForceWizard(false);
  };

  const handleConfigSaved = () => {
    loadCouncilConfig();
  };

  // ── Conversation handlers ───────────────────────────────────────────────

  // "New Conversation" now shows the CouncilPicker instead of immediately creating one
  const handleNewConversation = () => {
    if (isNewConversationBlocked) return;
    setCurrentConversation(null);
    setCurrentConversationId(null);
    setShowPicker(true);
  };

  // Called by CouncilPicker when user clicks "Start Conversation"
  const handleStartConversation = async (selectedModelIds) => {
    setIsCreatingConversation(true);
    try {
      const newConv = await api.createConversation(selectedModelIds);
      setConversations((prev) => [
        { id: newConv.id, created_at: newConv.created_at, title: newConv.title, message_count: 0 },
        ...prev,
      ]);
      setCurrentConversationId(newConv.id);
      setCurrentConversation(newConv);
      setShowPicker(false);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    } finally {
      setIsCreatingConversation(false);
    }
  };

  const handleCancelPicker = () => {
    setShowPicker(false);
  };

  const handleSelectConversation = (id) => {
    setShowPicker(false);
    setCurrentConversationId(id);
  };

  const handleSendMessage = async (content) => {
    if (!currentConversationId) return;

    setIsLoading(true);
    try {
      const userMessage = { role: 'user', content };
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
      }));

      const assistantMessage = {
        role: 'assistant',
        stage1: null,
        stage2: null,
        stage3: null,
        metadata: null,
        loading: { stage1: false, stage2: false, stage3: false },
      };

      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }));

      await api.sendMessageStream(currentConversationId, content, (eventType, event) => {
        switch (eventType) {
          case 'stage1_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              messages[messages.length - 1].loading.stage1 = true;
              return { ...prev, messages };
            });
            break;
          case 'stage1_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const last = messages[messages.length - 1];
              last.stage1 = event.data;
              last.loading.stage1 = false;
              return { ...prev, messages };
            });
            break;
          case 'stage2_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              messages[messages.length - 1].loading.stage2 = true;
              return { ...prev, messages };
            });
            break;
          case 'stage2_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const last = messages[messages.length - 1];
              last.stage2 = event.data;
              last.metadata = event.metadata;
              last.loading.stage2 = false;
              return { ...prev, messages };
            });
            break;
          case 'stage3_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              messages[messages.length - 1].loading.stage3 = true;
              return { ...prev, messages };
            });
            break;
          case 'stage3_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const last = messages[messages.length - 1];
              last.stage3 = event.data;
              last.loading.stage3 = false;
              return { ...prev, messages };
            });
            break;
          case 'title_complete':
            loadConversations();
            break;
          case 'complete':
            loadConversations();
            setIsLoading(false);
            break;
          case 'error':
            console.error('Stream error:', event.message);
            setIsLoading(false);
            break;
          default:
            console.log('Unknown event type:', eventType);
        }
      });
    } catch (error) {
      console.error('Failed to send message:', error);
      setCurrentConversation((prev) => ({
        ...prev,
        messages: prev.messages.slice(0, -2),
      }));
      setIsLoading(false);
    }
  };

  // ── Render ──────────────────────────────────────────────────────────────

  // Still checking auth status
  if (isAuthenticated === null) {
    return null;
  }

  // Not authenticated — show login/setup screen
  if (!isAuthenticated) {
    return <LoginScreen onAuthenticated={handleAuthenticated} />;
  }

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onOpenSettings={handleOpenSettings}
        onOpenWizard={handleOpenWizard}
        isNewConversationBlocked={isNewConversationBlocked}
        blockReason={blockReason}
      />

      {showPicker ? (
        <CouncilPicker
          config={councilConfig}
          onStart={handleStartConversation}
          onCancel={handleCancelPicker}
          onOpenWizard={handleOpenWizard}
          isCreating={isCreatingConversation}
        />
      ) : (
        <ChatInterface
          conversation={currentConversation}
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          warnings={blockingWarnings}
        />
      )}

      <Settings
        isOpen={showSettings}
        onClose={handleCloseSettings}
        onConfigSaved={handleConfigSaved}
        forceWizard={forceWizard}
      />
    </div>
  );
}

export default App;
