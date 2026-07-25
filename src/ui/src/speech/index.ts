export { isSpeechRecognitionSupported, getSpeechRecognitionConstructor } from "./support";
export { BrowserSpeechRecognitionService } from "./speechRecognition";
export { useSpeechRecognition } from "./useSpeechRecognition";
export {
  cancelSupervisorSpeech,
  getSpeakableSupervisorText,
  isSpeechSynthesisSupported,
  speakSupervisorResponse,
} from "./speechSynthesis";
export { useSupervisorSpeech } from "./useSupervisorSpeech";
export type { SupervisorSpeechControls } from "./useSupervisorSpeech";
export type {
  SpeechRecognitionApi,
  SpeechRecognitionControls,
  SpeechRecognitionOptions,
  SpeechRecognitionSnapshot,
  SpeechRecognitionConstructor,
  SpeechRecognitionLike,
} from "./types";
