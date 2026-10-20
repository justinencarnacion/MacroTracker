import styles from "./Discord.module.css";

export interface DiscordButton<T extends string> {
  value: T;
  label: string;
  emoji: string;
}

interface DiscordButtonsProps<T extends string> {
  buttons: DiscordButton<T>[];
  selected: T;
  onSelect: (value: T) => void;
  label: string;
}

/** A row of Discord-style buttons; the selected one is highlighted and disabled, like the bot's. */
export function DiscordButtons<T extends string>({ buttons, selected, onSelect, label }: DiscordButtonsProps<T>) {
  return (
    <div className={styles.buttons} role="group" aria-label={label}>
      {buttons.map((button) => {
        const isSelected = button.value === selected;
        return (
          <button
            key={button.value}
            type="button"
            className={`${styles.button} ${isSelected ? styles.buttonSelected : ""}`}
            aria-pressed={isSelected}
            disabled={isSelected}
            onClick={() => onSelect(button.value)}
          >
            <span aria-hidden="true">{button.emoji}</span> {button.label}
          </button>
        );
      })}
    </div>
  );
}
