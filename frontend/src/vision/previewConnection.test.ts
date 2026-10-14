import { describe, expect, it } from 'vitest';
import { effectiveConnectionState, previewInferenceUnavailable } from './previewConnection';

describe('isolated preview inference status', () => {
  it('marks only the explicit development preview URL as inference unavailable', () => {
    expect(previewInferenceUnavailable('?friday-preview=offline', true)).toBe(true);
    expect(previewInferenceUnavailable('?friday-preview=offline', false)).toBe(false);
    expect(previewInferenceUnavailable('?friday-preview=online', true)).toBe(false);
    expect(previewInferenceUnavailable('', true)).toBe(false);
  });

  it('preserves runtime connection state unless preview inference is explicitly unavailable', () => {
    expect(effectiveConnectionState('connected', false)).toBe('connected');
    expect(effectiveConnectionState('reconnecting', false)).toBe('reconnecting');
    expect(effectiveConnectionState('connected', true)).toBe('disconnected');
  });
});
