import "./App.css";

import { useFridayRuntime } from "./app";
import {
  ConversationComposer,
  NeuralCore,
} from "./components";

function App() {
  const {
    state,
    sendConversation,
  } = useFridayRuntime();

  return (
    <main
      className="friday-root"
      data-runtime-state={state.runtimeState}
      data-connection-state={state.connectionState}
    >
      <div className="space-layer space-layer-one" />
      <div className="space-layer space-layer-two" />
      <div className="vignette" />

      <header className="identity">
        <div className="identity-line" />
        <span className="identity-name">FRIDAY</span>
        <span className="identity-version">LOCAL INTELLIGENCE</span>
      </header>

      <NeuralCore state={state.runtimeState} />

      <ConversationComposer
        runtimeState={state.runtimeState}
        connectionState={state.connectionState}
        assistantText={state.assistantText}
        error={state.error}
        sendConversation={(prompt) =>
          sendConversation({
            prompt,
          })
        }
      />

      <footer className="system-strip">
        <div className="system-item">
          <span className="system-key">CORE</span>
          <span className="system-value">
            {state.runtimeState.toUpperCase().replaceAll("_", " ")}
          </span>
        </div>

        <div className="system-divider" />

        <div className="system-item">
          <span className="system-key">LINK</span>
          <span className="system-value">
            {state.connectionState.toUpperCase()}
          </span>
        </div>

        <div className="system-divider" />

        <div className="system-item">
          <span className="system-key">SESSION</span>
          <span className="system-value">
            {state.sessionId?.slice(0, 12) ?? "INITIALIZING"}
          </span>
        </div>
      </footer>
    </main>
  );
}

export default App;
