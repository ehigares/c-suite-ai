import { useState, useEffect, useMemo, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import CouncilPicker from './components/CouncilPicker';
import ChairmanPicker from './components/ChairmanPicker';
import SummarizationPicker from './components/SummarizationPicker';
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

  // 3-screen new conversation flow:
  //   'council' -> 'chairman' -> 'summarization' -> create conversation
  //   null = not in picker flow
  const [pickerScreen, setPickerScreen] = useState(null);
  const [pickerCouncilIds, setPickerCouncilIds] = useState([]);
  const [pickerChairmanId, setPickerChairmanId] = useState(null);
  const [isCreatingConversation, setIsCreatingConversation] = useState(false);

  // Global council config — drives warnings and CouncilPicker model list
  const [councilConfig, setCouncilConfig] = useState(null);

  // Register the auth-expired callback so api.js can trigger a logout
  // Bug 3 fix: also clear conversation state to prevent blank page
  const handleAuthExpired = useCallback(() => {
    setCurrentConversation(null);
    setCurrentConversationId(null);
    setPickerScreen(null);
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

  // After authentication, load data and restore last active conversation
  useEffect(() => {
    if (isAuthenticated) {
      loadConversations();
      loadCouncilConfig();
      // Bug 5 fix: restore last active conversation from localStorage
      const lastConvId = localStorage.getItem('lastActiveConversationId');
      if (lastConvId) {
        api.getConversation(lastConvId)
          .then((conv) => {
            setCurrentConversationId(lastConvId);
            setCurrentConversation(conv);
          })
          .catch(() => {
            // Conversation no longer exists — clear stored ID
            localStorage.removeItem('lastActiveConversationId');
          });
      }
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (currentConversationId && isAuthenticated) {
      loadConversation(currentConversationId);
      // Bug 5: persist last active conversation ID for restore after re-login
      localStorage.setItem('lastActiveConversationId', currentConversationId);
    }
  }, [currentConversationId, isAuthenticated]);

  // Track whether the user's existing password is too short (< 8 chars)
  const [passwordTooShort, setPasswordTooShort] = useState(false);

  const handleAuthenticated = (token, meta = {}) => {
    setToken(token);
    setIsAuthenticated(true);
    if (meta.passwordTooShort) {
      setPasswordTooShort(true);
    }
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
      // Bug 4 fix: if no models configured, auto-open wizard
      if ((cfg.available_models?.length ?? 0) === 0) {
        setForceWizard(true);
        setShowSettings(true);
      }
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

  // Non-blocking informational warnings (shown but don't prevent new conversations)
  const infoWarnings = useMemo(() => {
    const w = [];
    if (passwordTooShort) {
      w.push(
        'Your password is shorter than the new 8-character minimum. Please update it in Settings → Security.'
      );
    }
    return w;
  }, [passwordTooShort]);

  const allWarnings = useMemo(
    () => [...blockingWarnings, ...infoWarnings],
    [blockingWarnings, infoWarnings]
  );

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
    // If user changed their password in Settings, clear the too-short warning
    setPasswordTooShort(false);
  };

  // ── Conversation handlers ───────────────────────────────────────────────

  // "New Conversation" starts the 3-screen picker flow
  const handleNewConversation = () => {
    if (isNewConversationBlocked) return;
    setCurrentConversation(null);
    setCurrentConversationId(null);
    setPickerCouncilIds([]);
    setPickerChairmanId(null);
    setPickerScreen('council');
  };

  // Screen 1: Council selected → go to chairman picker
  const handleCouncilSelected = (selectedModelIds) => {
    setPickerCouncilIds(selectedModelIds);
    setPickerScreen('chairman');
  };

  // Screen 2: Chairman selected → go to summarization picker
  const handleChairmanSelected = (chairmanId) => {
    setPickerChairmanId(chairmanId);
    setPickerScreen('summarization');
  };

  // Screen 3: Summarization selected → create the conversation
  const handleSummarizationSelected = async (summarizationId) => {
    setIsCreatingConversation(true);
    try {
      const newConv = await api.createConversation(
        pickerCouncilIds,
        pickerChairmanId,
        summarizationId
      );
      setConversations((prev) => [
        { id: newConv.id, created_at: newConv.created_at, title: newConv.title, message_count: 0 },
        ...prev,
      ]);
      setCurrentConversationId(newConv.id);
      setCurrentConversation(newConv);
      setPickerScreen(null);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    } finally {
      setIsCreatingConversation(false);
    }
  };

  const handleCancelPicker = () => {
    setPickerScreen(null);
  };

  const handleSelectConversation = (id) => {
    setPickerScreen(null);
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

      {pickerScreen === 'council' ? (
        <CouncilPicker
          config={councilConfig}
          onStart={handleCouncilSelected}
          onCancel={handleCancelPicker}
          onOpenWizard={handleOpenWizard}
          isCreating={false}
        />
      ) : pickerScreen === 'chairman' ? (
        <ChairmanPicker
          models={councilConfig?.available_models ?? []}
          defaultId={councilConfig?.chairman_id ?? ''}
          onSelect={handleChairmanSelected}
          onBack={() => setPickerScreen('council')}
          onCancel={handleCancelPicker}
        />
      ) : pickerScreen === 'summarization' ? (
        <SummarizationPicker
          models={councilConfig?.available_models ?? []}
          defaultId={councilConfig?.summarization_model_id ?? ''}
          onSelect={handleSummarizationSelected}
          onBack={() => setPickerScreen('chairman')}
          onCancel={handleCancelPicker}
          isCreating={isCreatingConversation}
        />
      ) : (
        <ChatInterface
          conversation={currentConversation}
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          warnings={allWarnings}
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
