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
`;
