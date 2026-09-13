export type VisionView = 'home' | 'conversation' | 'learn' | 'map' | 'lab' | 'progress' | 'memory' | 'research' | 'objectives' | 'automations' | 'perception' | 'system';
export type CognitiveState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'working' | 'waiting' | 'error' | 'focus';
export interface WorkspaceProps {
  navigate: (view: VisionView) => void;
  notify: (message: string) => void;
  setCognition: (state: CognitiveState) => void;
}
