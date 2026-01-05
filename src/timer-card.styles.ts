// timer-card.styles.ts

import { css } from 'lit';

export const cardStyles = css`
  :host {
    display: block;
  }

  ha-card {
    padding: 0;
    position: relative;
    isolation: isolate;
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
    font-size: clamp(1.8rem, 10vw, 3.5rem);
    font-weight: bold;
    width: 100%;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.2;
    padding: 4px 44px;
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
    justify-content: space-between;
    margin-top: 12px;
    width: 100%;
    box-sizing: border-box;
    padding: 0 8px; /* Extra internal padding if needed, or rely on card padding */
    gap: 12px;
  }

  .slider-right-group {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    /* Reserve space so slider doesn't jump when label grows */
    min-width: 135px; 
    flex: 0 0 auto;
    white-space: nowrap;
  }

  .timer-slider {
    flex: 1; /* Fills remaining space */
    width: auto; /* Allow flex to control width */
    min-width: 100px; /* Don't shrink too small on tiny screens */
    height: 16px;
    margin: 0;
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
    font-size: 1.1em;
    font-weight: 400;
    color: var(--primary-text-color);
    white-space: nowrap;
    margin-left: 0px;
    margin-right: 10px;
    min-width: 75px; 
    text-align: center;
  }

  .timer-control-button {
      width: 50px;
      height: 38px;
      flex-shrink: 0;
      box-sizing: border-box;
      border-radius: 6px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: background-color 0.2s, opacity 0.2s;
      position: relative;     
      background-color: var(--secondary-background-color);
      border: none;
      box-shadow: none;
      
      color: var(--primary-color);
      --mdc-icon-size: 24px;
      padding: 0;
      margin-right: 10px; /* Add some spacing from the text */
  }

  .timer-control-button ha-icon[icon] {
      color: var(--primary-color);
  }

  .timer-control-button.reverse ha-icon[icon] {
      color: #f2ba5a;
  }



  .timer-control-button:hover {
      transform: none;
      box-shadow: 0 0 8px rgba(42, 182, 156, 1);
      color: var(--primary-color);
  }

  .timer-control-button:active {
      transform: none;
      box-shadow: 0 0 12px rgba(42, 182, 156, 0.6);
  }

  .timer-control-button.active {
      color: var(--primary-color);
  }



  @keyframes pulse {
      0%, 100% { box-shadow: 
          0 0 0 2px rgba(42, 137, 209, 0.3),
          0 0 12px rgba(42, 137, 209, 0.6); }
      50% { box-shadow: 
          0 0 0 4px rgba(42, 137, 209, 0.5),
          0 0 20px rgba(42, 137, 209, 0.8); }
  }

  .timer-control-button.active.reverse {
      color: #f2ba5a;
  }

  .timer-control-button.disabled {
    opacity: 0.5;
    cursor: not-allowed;
    box-shadow: none;
  }
  
  .timer-control-button.disabled:hover {
    transform: none;
    box-shadow: none;
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
    gap: 10px;
    justify-content: center;
    padding-bottom: 24px;
    margin-top: 0px;
  }

  .timer-button {
    width: 80px;
    height: 38px;
    border-radius: 6px;
    display: flex;
    flex-direction: row;
    align-items: baseline;
    justify-content: center;
    gap: 4px;
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

  .timer-button.stop-button.active,
  .timer-button.stop-button.active:hover {
    box-shadow: none;
    border: none;
  }

  .timer-button-value {
    font-size: 1.1em;
    font-weight: 400;
    line-height: 38px;
  }

  .timer-button-unit {
    font-size: 0.9em;
    font-weight: 400;
    margin-top: 0px;
    line-height: 38px;
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
    margin: 35px 0 12px 0;
    padding-right: 50px;
    border-radius: 0;
  }

  /* Push banner down further if there is no title to clear the power button */
  .card-header:not(.has-title) + .watchdog-banner {
    margin-top: 60px;
  }

  .entity-state-button {
    position: absolute;
    top: 12px;
    left: 16px;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    background-color: transparent;
    color: var(--secondary-text-color);
    transition: all 0.3s ease;
    z-index: 5;
    /* No border or shadow in default state */
  }

  .entity-state-button ha-icon {
    --mdc-icon-size: 30px;
    color: var(--secondary-text-color);
  }

  .entity-state-button:hover {
    background-color: rgba(255, 255, 255, 0.05);
    transform: scale(1.1);
  }

  .entity-state-button:active {
    transform: scale(0.95);
  }

  .entity-state-button.on {
    color: var(--primary-color);
    /* Circular glow effect */
    box-shadow: 0 0 15px var(--primary-color);
    background-color: rgba(var(--rgb-primary-color), 0.1);
    animation: glow-pulse 2s infinite;
  }
  
  .entity-state-button.on ha-icon {
    color: var(--primary-color);
  }

  @keyframes glow-pulse {
      0%, 100% { box-shadow: 0 0 15px rgba(var(--rgb-primary-color), 0.6); }
      50% { box-shadow: 0 0 25px rgba(var(--rgb-primary-color), 0.9); }
  }

  .entity-state-button.on.reverse {
    color: #f2ba5a;
    box-shadow: 0 0 15px #f2ba5a;
    background-color: rgba(242, 186, 90, 0.1);
    animation: glow-pulse-orange 2s infinite;
  }
  
  .entity-state-button.on.reverse ha-icon {
      color: #f2ba5a;
  }

  @keyframes glow-pulse-orange {
      0%, 100% { box-shadow: 0 0 15px rgba(242, 186, 90, 0.6); }
      50% { box-shadow: 0 0 25px rgba(242, 186, 90, 0.9); }
  }


  `;