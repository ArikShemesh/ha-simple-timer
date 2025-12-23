// timer-card-editor.styles.ts

import { css } from 'lit';

export const editorCardStyles = css`
      .card-config-group {
        padding: 16px;
        background-color: var(--card-background-color);
        border-top: 1px solid var(--divider-color);
        margin-top: 16px;
      }
      h3 {
        margin-top: 0;
        margin-bottom: 16px;
        font-size: 1.1em;
        font-weight: normal;
        color: var(--primary-text-color);
      }
      .checkbox-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(70px, 1fr));
        gap: 8px 16px;
        margin-bottom: 16px;
      }
      @media (min-width: 400px) {
        .checkbox-grid {
          grid-template-columns: repeat(5, 1fr);
        }
      }
      .checkbox-label {
        display: flex;
        align-items: center;
        cursor: pointer;
        color: var(--primary-text-color);
      }
      .checkbox-label input[type="checkbox"] {
        margin-right: 8px;
        min-width: 20px;
        min-height: 20px;
      }
      .timer-buttons-info {
        padding: 12px;
        background-color: var(--secondary-background-color);
        border-radius: 8px;
        border: 1px solid var(--divider-color);
      }
      .timer-buttons-info p {
        margin: 4px 0;
        font-size: 14px;
        color: var(--primary-text-color);
      }
      .warning-text {
        color: var(--warning-color);
        font-weight: bold;
      }
      .info-text {
        color: var(--primary-text-color);
        font-style: italic;
      }
      
      .card-config {
        padding: 16px;
      }
      .config-row {
        margin-bottom: 16px;
      }
      .config-row ha-textfield,
      .config-row ha-select {
        width: 100%;
      }
      .config-row ha-formfield {
        display: flex;
        align-items: center;
      }

      /* Timer Chips UI */
      .timer-chips-container {
        margin-bottom: 8px;
      }

      .chips-wrapper {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        min-height: 40px;
        padding: 8px 0;
      }

      .timer-chip {
        display: flex;
        align-items: center;
        background-color: var(--secondary-background-color);
        border: 1px solid var(--divider-color);
        border-radius: 16px;
        padding: 4px 12px;
        font-size: 14px;
        color: var(--primary-text-color);
        transition: background-color 0.2s;
      }

      .timer-chip:hover {
        background-color: var(--secondary-text-color);
        color: var(--primary-background-color);
      }

      .remove-chip {
        margin-left: 8px;
        cursor: pointer;
        font-weight: bold;
        opacity: 0.6;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 16px;
        border-radius: 50%;
      }

      .remove-chip:hover {
        opacity: 1;
        background-color: rgba(0,0,0,0.1);
      }

      .add-timer-row {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 8px;
      }

      .add-btn {
        background-color: var(--primary-color);
        color: var(--text-primary-color);
        padding: 0 16px;
        height: 56px; /* Match textfield height */
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 4px;
        cursor: pointer;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: -6px; /* Align slightly better with textfield label offset */
      }
      .add-btn:hover {
        opacity: 0.9;
      }
      .add-btn:active {
        opacity: 0.7;
      }
`;