// timer-card.styles.ts

import { css } from 'lit';

export const cardStyles = css`
  :host {
    display: block;
  }

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

  .card-header.has-title {
      margin-bottom: -15px;
  }
    
  .card-title {
    font-family: 'Roboto', sans-serif;
    font-weight: 500;
    font-size: 1.7rem;
    color: rgba(160,160,160,0.7);
    text-align: left;
    margin: 0;
    padding: 0 8px;
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
    text-align: center;
    padding: 0 !important;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }

  .countdown-display {
    display: flex;
    justify-content: center;
    align-items: center;
    font-size: 3.5rem;
    font-weight: bold;
    width: 100%;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.2;
    padding: 4px 0;
    min-height: 3.5rem;
    box-sizing: border-box;
  }
    
  .countdown-display.active {
    color: var(--primary-color);
  }

  .countdown-display.active.reverse {
    color: #f2ba5a;
  }

  .daily-usage-display {
    font-size: 1rem;
    color: var(--secondary-text-color);
    text-align: center;
    margin-top: -8px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
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
    background: #2ab69c;
    cursor: pointer;
    border: 2px solid #4bd9bf;
    box-shadow: 
      0 0 0 2px rgba(75, 217, 191, 0.3),
      0 0 8px rgba(42, 182, 156, 0.4),
      0 2px 4px rgba(0, 0, 0, 0.2);
    transition: all 0.2s ease;
  }

  .timer-slider::-webkit-slider-thumb:hover {
    background: #239584;
    border: 2px solid #4bd9bf;
    box-shadow: 
      0 0 0 3px rgba(75, 217, 191, 0.4),
      0 0 12px rgba(42, 182, 156, 0.6),
      0 2px 6px rgba(0, 0, 0, 0.3);
    transform: scale(1.05);
  }

  .timer-slider::-webkit-slider-thumb:active {
    background: #1e7e6f;
    border: 2px solid #4bd9bf;
    box-shadow: 
      0 0 0 4px rgba(75, 217, 191, 0.5),
      0 0 16px rgba(42, 182, 156, 0.7),
      0 2px 8px rgba(0, 0, 0, 0.4);
    transform: scale(0.98);
  }

  .timer-slider::-moz-range-thumb {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: #2ab69c;
    cursor: pointer;
    border: 2px solid #4bd9bf;
    box-shadow: 
      0 0 0 2px rgba(75, 217, 191, 0.3),
      0 0 8px rgba(42, 182, 156, 0.4),
      0 2px 4px rgba(0, 0, 0, 0.2);
    transition: all 0.2s ease;
  }

  .timer-slider::-moz-range-thumb:hover {
    background: #239584;
    border: 2px solid #4bd9bf;
    box-shadow: 
      0 0 0 3px rgba(75, 217, 191, 0.4),
      0 0 12px rgba(42, 182, 156, 0.6),
      0 2px 6px rgba(0, 0, 0, 0.3);
    transform: scale(1.05);
  }

  .timer-slider::-moz-range-thumb:active {
    background: #1e7e6f;
    border: 2px solid #4bd9bf;
    box-shadow: 
      0 0 0 4px rgba(75, 217, 191, 0.5),
      0 0 16px rgba(42, 182, 156, 0.7),
      0 2px 8px rgba(0, 0, 0, 0.4);
    transform: scale(0.98);
  }

  .slider-label {
    font-size: 16px;
    font-weight: 500;
    color: var(--primary-text-color);
    min-width: 60px;
    text-align: left;
  }

  .power-button-small {
      width: 65px;
      height: 60px;
      flex-shrink: 0;
      box-sizing: border-box;
      border-radius: 12px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;     
      background-color: var(--secondary-background-color);
      border: 2px solid transparent;
      background-clip: padding-box;
      box-shadow: 
          0 8px 25px rgba(0, 0, 0, 0.4),
          0 3px 10px rgba(0, 0, 0, 0.3),
          inset 0 1px 0 rgba(255, 255, 255, 0.2),
          inset 0 -1px 0 rgba(0, 0, 0, 0.3);
      
      color: var(--primary-color);
      --mdc-icon-size: 36px;
      padding: 4px;
  }

  .power-button-small ha-icon[icon] {
      color: var(--primary-color);
  }

  .power-button-small.reverse ha-icon[icon] {
      color: #f2ba5a;
  }

  .power-button-small::before {
      content: '';
      position: absolute;
      inset: -2px;
      border-radius: 14px;
      z-index: -1;
  }

  .power-button-small:hover {
      transform: translateY(-2px);
      box-shadow: 
          0 12px 35px rgba(0, 0, 0, 0.5),
          0 5px 15px rgba(0, 0, 0, 0.4),
          inset 0 1px 0 rgba(255, 255, 255, 0.25),
          inset 0 -1px 0 rgba(0, 0, 0, 0.3);
      color: var(--primary-color);
  }

  .power-button-small:active {
      transform: translateY(0px);
      transition: all 0.1s;
      box-shadow: 
          0 4px 15px rgba(0, 0, 0, 0.4),
          0 2px 5px rgba(0, 0, 0, 0.3),
          inset 0 1px 0 rgba(255, 255, 255, 0.15),
          inset 0 -1px 0 rgba(0, 0, 0, 0.4);
  }

  .power-button-small.on {
      border: 2px solid #4da3e0;
      color: var(--primary-color);
      box-shadow: 
          0 0 0 2px rgba(42, 137, 209, 0.3),
          0 0 12px rgba(42, 137, 209, 0.6);
      animation: pulse 2s infinite;
  }

  .power-button-small.on::before {
      display: none;
  }

  @keyframes pulse {
      0%, 100% { box-shadow: 
          0 0 0 2px rgba(42, 137, 209, 0.3),
          0 0 12px rgba(42, 137, 209, 0.6); }
      50% { box-shadow: 
          0 0 0 4px rgba(42, 137, 209, 0.5),
          0 0 20px rgba(42, 137, 209, 0.8); }
  }

  .power-button-small.on.reverse {
      border: 2px solid #f4c474;
      color: #f2ba5a;
      box-shadow: 
          0 0 0 2px rgba(242, 186, 90, 0.3),
          0 0 12px rgba(242, 186, 90, 0.6);
      animation: pulse-orange 2s infinite;
  }

  @keyframes pulse-orange {
      0%, 100% { box-shadow: 
          0 0 0 2px rgba(242, 186, 90, 0.3),
          0 0 12px rgba(242, 186, 90, 0.6); }
      50% { box-shadow: 
          0 0 0 4px rgba(242, 186, 90, 0.5),
          0 0 20px rgba(242, 186, 90, 0.8); }
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
    box-shadow: 0 0 8px rgba(42, 182, 156, 1);
  }

  .timer-button.active {
    color: white;
    box-shadow: 0 0 8px rgba(42, 182, 156, 1);
  }

  .timer-button.active:hover {
    box-shadow: 0 0 12px rgba(42, 182, 156, 0.6);
  }

  .timer-button.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .timer-button.disabled:hover {
    box-shadow: none;
    opacity: 0.5;
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

  .power-button-top-right {
    position: absolute;
    top: 12px;
    right: 12px;
    width: 40px;
    height: 40px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    background-color: var(--secondary-background-color);
    color: var(--primary-color);
    box-shadow: 
      0 2px 5px rgba(0, 0, 0, 0.2),
      inset 0 1px 0 rgba(255, 255, 255, 0.1);
    transition: all 0.2s ease;
    z-index: 5;
  }

  .power-button-top-right ha-icon {
    --mdc-icon-size: 24px;
    color: var(--primary-color);
  }

  .power-button-top-right:hover {
    background-color: var(--primary-background-color);
    transform: scale(1.05);
  }

  .power-button-top-right:active {
    transform: scale(0.95);
  }

  .power-button-top-right.on {
    color: var(--primary-color);
    box-shadow: 0 0 8px rgba(42, 137, 209, 0.6);
    border: 1px solid rgba(42, 137, 209, 0.5);
    animation: pulse 2s infinite;
  }
  `;