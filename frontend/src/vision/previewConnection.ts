export function previewInferenceUnavailable(search: string, isDevelopment: boolean): boolean {
  const query = search.startsWith('?') ? search.slice(1) : search;
  return isDevelopment && new URLSearchParams(query).get('friday-preview') === 'offline';
}

export function effectiveConnectionState(runtimeState: string, inferenceUnavailable: boolean): string {
  return inferenceUnavailable ? 'disconnected' : runtimeState;
}
