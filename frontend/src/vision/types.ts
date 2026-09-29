export type VisionView = 'home' | 'settings' | 'conversation' | 'learn' | 'map' | 'lab' | 'projects' | 'interview' | 'progress' | 'memory' | 'research' | 'objectives' | 'automations' | 'history' | 'perception' | 'system';
export type CognitiveState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'working' | 'waiting' | 'error' | 'focus';
export interface WorkspaceProps {
  navigate: (view: VisionView) => void;
  notify: (message: string) => void;
  setCognition: (state: CognitiveState) => void;
}
