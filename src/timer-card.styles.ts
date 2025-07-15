// timer-card.styles.ts

import { css } from 'lit';

export const cardStyles = css`
      :host { display: block; }
      ha-card {
        padding: 0;
        position: relative; /* Needed for absolute positioning of the repo link */
      }
      .card-header {
        display: flex;
        justify-content: center;
        align-items: center;
        font-size: 1.2em;
        font-weight: bold;
        text-align: center;
        padding: 12px;
        background-color: var(--primary-color-faded, rgba(150, 210, 230, 0.2));
        border-bottom: 1px solid var(--divider-color);
        color: var(--primary-text-color);
        border-radius: 12px 12px 0 0;
        margin-bottom: 12px;
      }
      .card-title {
        flex-grow: 1;
        white-space: pre-wrap;
        word-break: break-word;
      }
      .repo-link {
        position: absolute;
        top: 12px;
        right: 12px;
        color: var(--secondary-text-color);
        z-index: 1;
      }
      .repo-link:hover {
        color: var(--primary-color);
      }
      .placeholder { padding: 16px; background-color: var(--secondary-background-color); }
      .warning { padding: 16px; color: white; background-color: var(--error-color); }
      .main-grid, .button-grid { gap: 12px; padding: 12px; }
      .main-grid { display: grid; grid-template-columns: 1fr 1fr; }
      .button-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(90px, 1fr)); padding-top: 0; }
      .button {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 16px 8px;
        background-color: var(--secondary-background-color);
        border-radius: 12px;
        cursor: pointer;
        transition: background-color 0.2s, opacity 0.2s;
        text-align: center;
        -webkit-tap-highlight-color: transparent;
        height: 100px;
        box-sizing: border-box;
      }
      .button:hover { background-color: var(--primary-color-faded, #3a506b); }
      .power-button {
        font-size: 80px;
        --mdc-icon-size: 80px;
        color: white;
        background-color: var(--error-color);
      }
      .power-button.on { background-color: var(--success-color); }
      .readonly {
        background-color: var(--card-background-color);
        border: 1px solid var(--secondary-background-color);
        line-height: 1.2;
        cursor: default;
      }
      .active, .active:hover { background-color: var(--primary-color); color: white; }
      .countdown-text { font-size: 28px; font-weight: bold; color: white; }
      .daily-time-text {
        font-size: 36px;
        font-weight: bold;
      }
      .daily-time-text.with-seconds {
        font-size: 28px;
      }
      .runtime-label { font-size: 14px; text-transform: uppercase; color: var(--secondary-text-color); margin-top: 2px; }
      .timer-button-content { display: flex; flex-direction: column; align-items: center; justify-content: center; line-height: 1.1; }
      .timer-button-value { font-size: 36px; font-weight: 500; color: var(--primary-text-color); }
      .timer-button-unit { font-size: 14px; color: var(--secondary-text-color); }
      .active .timer-button-value, .active .timer-button-unit { color: white; }
      .disabled { opacity: 0.5; cursor: not-allowed; }
      .disabled:hover { background-color: var(--secondary-background-color); }
      .status-message {
        display: flex;
        align-items: center;
        padding: 8px 12px;
        margin: 0 12px 12px 12px;
        border-radius: 8px;
        border: 1px solid var(--warning-color);
        background-color: rgba(var(--rgb-warning-color), 0.1);
      }
      .status-icon { color: var(--warning-color); margin-right: 8px; }
      .status-text { font-size: 14px; color: var(--primary-text-color); }
      .watchdog-banner {
        margin: 0 0 12px 0;
        border-radius: 0;
        grid-column: 1 / -1;
      }
      .status-message.warning {
        display: flex;
        align-items: center;
        padding: 8px 12px;
        margin: 0 12px 12px 12px;
        border-radius: 8px;
        border: 1px solid var(--warning-color);
        background-color: rgba(var(--rgb-warning-color), 0.1);
      }
      .status-icon {
        color: var(--warning-color);
        margin-right: 8px;
      }
      .status-text {
        font-size: 14px;
        color: var(--primary-text-color);
      }
`;
