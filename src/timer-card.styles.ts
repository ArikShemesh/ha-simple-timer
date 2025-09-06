// timer-card.styles.ts

import { css } from 'lit';

export const cardStyles = css`
      :host { display: block; }
      ha-card {
        padding: 0;
        position: relative;
      }
			
      .card-header {
        display: flex;
        justify-content: center;
        align-items: center;
        font-size: 1.5em;
        font-weight: bold;
        text-align: center;
        padding: 0px;
        color: var(--primary-text-color);
        border-radius: 12px 12px 0 0;
				margin-bottom: 0px;
      }
      .card-title {
        flex-grow: 1;
        white-space: pre-wrap;
        word-break: break-word;
      }
      .repo-link {
        position: absolute;
        top: 0px;
        right: 12px;
        color: var(--secondary-text-color);
        z-index: 1;
      }
      .repo-link:hover {
        color: var(--primary-color);
      }
      .placeholder { 
        padding: 16px; 
        background-color: var(--secondary-background-color); 
      }
      .warning { 
        padding: 16px; 
        color: white; 
        background-color: var(--error-color); 
      }
      
      /* New layout styles */
      .card-content {
				padding: 12px !important;
				padding-top: 0px !important;
				margin: 0 !important;
			}
      
      .countdown-section {
				min-height: 60px;
				text-align: center;
				padding: 0 !important;
				display: flex;
				align-items: center;
				justify-content: center;
			}
      
      .countdown-display {
				font-size: 48px;
				font-weight: bold;
				color: var(--primary-text-color);
				font-family: 'Roboto Mono', monospace;
				margin: 0 !important;
				padding: 0 !important;
			}
      
      .countdown-display.active {
        color: var(--primary-color);
      }
      
      .slider-row {
				display: flex;
				align-items: center;
				gap: 4px;
				margin-bottom: 15px;
				flex-wrap: wrap;
				justify-content: center;
			}
      
      .slider-container {
        flex: 0 0 75%;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      
      .timer-slider {
        flex: 1;
        height: 20px;
        -webkit-appearance: none;
        appearance: none;
        background: var(--secondary-background-color);
        border-radius: 20px;
        outline: none;
      }
      
      .timer-slider::-webkit-slider-thumb {
        -webkit-appearance: none;
        appearance: none;
        width: 30px;
        height: 30px;
        border-radius: 50%;
        background: var(--primary-color);
        cursor: pointer;
      }
      
      .timer-slider::-moz-range-thumb {
        width: 30px;
        height: 30px;
        border-radius: 50%;
        background: var(--primary-color);
        cursor: pointer;
        border: none;
      }
      
      .slider-label {
        font-size: 16px;
        font-weight: 500;
        color: var(--primary-text-color);
        min-width: 60px;
        text-align: left;
      }
      
      .power-button-small {
				border-radius: 12px;
				display: flex;
				flex-direction: column;  /* Stack icon and text vertically */
				align-items: center;
				justify-content: center;
				cursor: pointer;
				transition: background-color 0.2s;
				background-color: var(--error-color);
				color: white;
				font-size: 24px;  /* Smaller icon */
				--mdc-icon-size: 35px;
				padding: 6px;
			}
      
      .power-button-small.on {
				background-color: var(--success-color);
			}
			
			.power-usage-text {
				font-size: 14px;
				font-weight: 500;
				margin-top: 2px;
				line-height: 1;
				text-align: center;
			}
      
      .button-grid {
        display: flex;
				flex-wrap: wrap;
        gap: 8px;
        justify-content: center;
      }
      
      .timer-button {
        width: 80px;
        height: 65px;
        border-radius: 12px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: background-color 0.2s, opacity 0.2s;
        text-align: center;
        background-color: var(--secondary-background-color);
        color: var(--primary-text-color);
      }
      
      .timer-button:hover {
        background-color: var(--primary-color-faded, #3a506b);
      }
      
      .timer-button.active {
        background-color: var(--primary-color);
        color: white;
      }
      
      .timer-button.active:hover {
        background-color: var(--primary-color);
      }
      
      .timer-button.disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      
      .timer-button.disabled:hover {
        background-color: var(--secondary-background-color);
      }
      
      .timer-button-value {
        font-size: 20px;
        font-weight: 600;
        line-height: 1;
      }
      
      .timer-button-unit {
        font-size: 12px;
        font-weight: 400;
        margin-top: 2px;
      }
      
      .status-message {
        display: flex;
        align-items: center;
        padding: 8px 12px;
        margin: 0 0 12px 0;
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
      
      .watchdog-banner {
        margin: 0 0 12px 0;
        border-radius: 0;
      }
`;