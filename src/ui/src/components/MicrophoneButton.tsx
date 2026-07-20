import type { ButtonHTMLAttributes } from "react";

export interface MicrophoneButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onClick" | "children"> {
  isListening: boolean;
  disabled?: boolean;
  onToggle: () => void;
}

/**
 * Toggle control that starts or stops listening and reflects current state.
 */
export function MicrophoneButton({
  isListening,
  disabled = false,
  onToggle,
  className,
  ...rest
}: MicrophoneButtonProps) {
  const label = isListening ? "Stop listening" : "Start listening";

  return (
    <button
      type="button"
      className={["mic-button", isListening ? "mic-button--listening" : "", className]
        .filter(Boolean)
        .join(" ")}
      aria-pressed={isListening}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onToggle}
      data-testid="microphone-button"
      data-listening={isListening ? "true" : "false"}
      {...rest}
    >
      <span className="mic-button__inner">
        <span aria-hidden="true" className="mic-button__icon">
          <span className="material-symbols-outlined">mic</span>
        </span>
      </span>
      <span className="mic-button__label">{label}</span>
    </button>
  );
}
