import { vi } from "vitest";

export interface MockSpeechSynthesisHandles {
  speak: ReturnType<typeof vi.fn>;
  cancel: ReturnType<typeof vi.fn>;
  getVoices: ReturnType<typeof vi.fn>;
}

export function installMockSpeechSynthesis(): MockSpeechSynthesisHandles {
  const speak = vi.fn();
  const cancel = vi.fn();
  const getVoices = vi.fn(() => []);

  class MockSpeechSynthesisUtterance {
    text: string;
    rate = 1;
    voice: SpeechSynthesisVoice | null = null;

    constructor(text: string) {
      this.text = text;
    }
  }

  vi.stubGlobal("SpeechSynthesisUtterance", MockSpeechSynthesisUtterance);
  vi.stubGlobal("speechSynthesis", {
    speak,
    cancel,
    getVoices,
    onvoiceschanged: null,
  });

  return { speak, cancel, getVoices };
}

export function removeMockSpeechSynthesis(): void {
  vi.unstubAllGlobals();
}
