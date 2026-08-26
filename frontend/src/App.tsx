import "./App.css";

import { useFridayRuntime } from "./app";

function App() {
  const { state } = useFridayRuntime();

  return (
    <main
      className="friday-root"
      data-runtime-state={state.runtimeState}
      data-connection-state={state.connectionState}
    >
      <div
        className="friday-shell"
        aria-label="Friday interface"
      />
    </main>
  );
}

export default App;
