import {
  useEffect,
  useMemo,
  useSyncExternalStore,
} from "react";

import {
  FridayRuntimeClient,
  FridayRuntimeStore,
} from "../runtime";
import type {
  ConversationRequest,
  FridayRuntimeViewState,
} from "../runtime";

export interface UseFridayRuntimeResult {
  state: FridayRuntimeViewState;
  sendConversation: (
    request: ConversationRequest,
    signal?: AbortSignal,
  ) => Promise<void>;
}

export function useFridayRuntime(
  baseUrl = "",
): UseFridayRuntimeResult {
  const store = useMemo(
    () => new FridayRuntimeStore(
      new FridayRuntimeClient(baseUrl),
    ),
    [baseUrl],
  );

  const state = useSyncExternalStore(
    (listener) => store.subscribe(listener),
    () => store.getSnapshot(),
    () => store.getSnapshot(),
  );

  useEffect(() => {
    const controller = new AbortController();

    void store.start(controller.signal).catch(() => {
      // The store already exposes connection/error state.
    });

    return () => {
      controller.abort();
      store.stop();
    };
  }, [store]);

  return {
    state,
    sendConversation: (
      request: ConversationRequest,
      signal?: AbortSignal,
    ) => store.sendConversation(request, signal),
  };
}
