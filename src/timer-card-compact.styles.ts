// timer-card-compact.styles.ts
//
// Styles for `layout: compact` only. Everything is scoped under
// `ha-card.compact`, so the classic layout is untouched. Colors come from the
// theme; the card's color options override them in `_getCompactStyle()`.

import { css } from 'lit';

export const compactStyles = css`
  ha-card.compact {
    /* Beats the classic \`ha-card { padding: 0 0 var(--st-edge) }\`. Bottom
       spacing is added back only when something sits under the main row. */
    padding: 0;
    overflow: hidden;
    --st-fill: rgba(var(--rgb-primary-text-color, 225, 225, 225), 0.08);
    --st-on: var(--state-switch-active-color, var(--amber-color, #ffc107));
    --st-accent: var(--primary-color);
    --st-reverse: var(--orange-color, #ff9800);
  }

  ha-card.compact.has-extra {
    padding-bottom: 10px;
  }

  /* Narrow arrangement (half of a narrow section, ~180px). The card is the
     query container, so this follows the card's own width, not the screen. */
  ha-card.compact {
    container-type: inline-size;
  }

  .c-left { display: none; }

  /* :where() keeps this reset at element specificity, so each button's own
     class (padding, background) still wins over it. */
  :where(ha-card.compact) button {
    font-family: inherit;
    border: 0;
    margin: 0;
    padding: 0;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
  }

  .c-row {
    display: flex;
    align-items: center;
    gap: 10px;
    height: 56px;
    padding: 0 10px;
    box-sizing: border-box;
  }

  .c-icon {
    width: 36px;
    height: 36px;
    flex: none;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--st-fill);
    color: var(--secondary-text-color);
    --mdc-icon-size: 22px;
    transition: background-color 180ms, color 180ms;
  }

  .c-icon.on {
    background: color-mix(in srgb, var(--st-on) 20%, transparent);
    color: var(--st-on);
  }

  .c-info {
    flex: 1;
    min-width: 0;
    cursor: pointer;
  }

  .c-name {
    font-size: 14px;
    font-weight: 500;
    line-height: 20px;
    letter-spacing: 0.1px;
    color: var(--primary-text-color);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .c-sec {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    line-height: 16px;
    color: var(--secondary-text-color);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .c-sec ha-icon {
    --mdc-icon-size: 13px;
    flex: none;
  }

  .c-sec-text {
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .c-time {
    flex: none;
    font-size: 22px;
    font-weight: 500;
    color: var(--st-accent);
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.2px;
    cursor: pointer;
    user-select: none;
    -webkit-user-select: none;
  }

  .c-time.reverse { color: var(--st-reverse); }

  .c-act {
    width: 40px;
    height: 40px;
    flex: none;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--st-fill);
    color: var(--primary-text-color);
    --mdc-icon-size: 20px;
  }

  .c-act.ghost {
    background: transparent;
    color: var(--secondary-text-color);
    --mdc-icon-size: 22px;
  }

  .c-act.ctl { color: var(--st-accent); }
  .c-act.ctl.reverse { color: var(--st-reverse); }

  .c-pill {
    height: 36px;
    flex: none;
    padding: 0 14px;
    border-radius: 18px;
    display: flex;
    align-items: center;
    gap: 4px;
    background: color-mix(in srgb, var(--st-accent) 20%, transparent);
    color: var(--st-accent);
    font-size: 14px;
    font-weight: 500;
    --mdc-icon-size: 16px;
  }

  .c-pill.reverse {
    background: color-mix(in srgb, var(--st-reverse) 20%, transparent);
    color: var(--st-reverse);
  }

  .c-feat {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 0 10px;
  }

  .c-chip {
    flex: 1 1 48px;
    min-width: 48px;
    height: 36px;
    border-radius: 10px;
    background: var(--st-fill);
    color: var(--primary-text-color);
    font-size: 13px;
    font-weight: 500;
    white-space: nowrap;
  }

  .c-chip.sel {
    background: color-mix(in srgb, var(--st-accent) 20%, transparent);
    color: var(--st-accent);
  }

  .c-panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 10px 10px 0;
  }

  .c-slider-row {
    display: flex;
    gap: 8px;
  }

  .c-range-wrap {
    position: relative;
    flex: 1;
    min-width: 0;
    height: 42px;
  }

  .c-range {
    -webkit-appearance: none;
    appearance: none;
    width: 100%;
    height: 42px;
    margin: 0;
    border-radius: 12px;
    outline: none;
    cursor: pointer;
    background: linear-gradient(
      to right,
      var(--st-range-fill, color-mix(in srgb, var(--st-accent) 60%, transparent)) 0 var(--st-pct, 0%),
      var(--st-range-track, var(--st-fill)) var(--st-pct, 0%) 100%
    );
  }

  .c-range:focus-visible {
    box-shadow: 0 0 0 2px var(--st-accent);
  }

  .c-range::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 4px;
    height: 22px;
    border-radius: 2px;
    background: #fff;
    border: 0;
    box-shadow: none;
  }

  .c-range::-moz-range-thumb {
    width: 4px;
    height: 22px;
    border-radius: 2px;
    background: #fff;
    border: 0;
    box-shadow: none;
  }

  .c-range-label {
    position: absolute;
    left: 14px;
    top: 0;
    line-height: 42px;
    font-size: 14px;
    font-weight: 500;
    color: var(--primary-text-color);
    pointer-events: none;
  }

  .c-start {
    height: 42px;
    flex: none;
    padding: 0 16px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    gap: 4px;
    background: var(--st-accent);
    color: var(--text-primary-color, #fff);
    font-size: 14px;
    font-weight: 500;
    --mdc-icon-size: 18px;
  }

  .c-start.reverse { background: var(--st-reverse); }

  .c-start:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* The shared schedule panel, sized for the compact padding. */
  .c-panel .schedule-toggle {
    margin: 0;
    padding: 8px 0 0;
    justify-content: flex-start;
  }
  .c-panel .schedule-panel { margin: 0; padding-top: 0; }
  .c-panel .schedule-panel .schedule-toggle { margin: 0 0 12px; }

  ha-card.compact .status-message {
    margin: 0 10px;
  }
  ha-card.compact .c-row + .status-message,
  ha-card.compact .c-feat + .status-message,
  ha-card.compact .c-panel + .status-message {
    margin-top: 10px;
  }
  ha-card.compact .status-message + .c-feat {
    margin-top: 10px;
  }

  .c-bar {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 3px;
    background: var(--st-fill);
    pointer-events: none;
  }

  .c-bar > div {
    height: 100%;
    background: var(--st-accent);
    transition: width 1s linear;
  }

  .c-bar.reverse > div { background: var(--st-reverse); }

  /* Narrow arrangement. Must stay LAST: these rules have the same specificity
     as the base rules above and win only by coming after them. */
  @container (max-width: 260px) {
    /* The big countdown leaves the row and becomes the second line, so the
       name keeps its room. */
    .c-time { display: none; }
    .c-sec-text.wide-only { display: none; }
    .c-left {
      display: inline;
      color: var(--st-accent);
      font-weight: 500;
      font-variant-numeric: tabular-nums;
    }
    .c-left.reverse { color: var(--st-reverse); }
    /* "▶ 20 min" goes: it only exists when the slider is enabled, so the
       chevron is always there to open the slider and its Start button. */
    .c-pill { display: none; }
    /* With a schedule armed the row already holds the cancel X; the extra
       chevron would squeeze the name to nothing. */
    .c-armed-chev { display: none; }
    .c-row { gap: 8px; }
    .c-start { padding: 0 12px; }
  }
`;
