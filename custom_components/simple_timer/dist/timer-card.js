/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const t=globalThis,e=t.ShadowRoot&&(void 0===t.ShadyCSS||t.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,i=Symbol(),o=new WeakMap;let n=class{constructor(t,e,o){if(this._$cssResult$=!0,o!==i)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o;const i=this.t;if(e&&void 0===t){const e=void 0!==i&&1===i.length;e&&(t=o.get(i)),void 0===t&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),e&&o.set(i,t))}return t}toString(){return this.cssText}};const r=(t,...e)=>{const o=1===t.length?t[0]:e.reduce((e,i,o)=>e+(t=>{if(!0===t._$cssResult$)return t.cssText;if("number"==typeof t)return t;throw Error("Value passed to 'css' function must be a 'css' function result: "+t+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+t[o+1],t[0]);return new n(o,t,i)},s=e?t=>t:t=>t instanceof CSSStyleSheet?(t=>{let e="";for(const i of t.cssRules)e+=i.cssText;return(t=>new n("string"==typeof t?t:t+"",void 0,i))(e)})(t):t,{is:a,defineProperty:l,getOwnPropertyDescriptor:d,getOwnPropertyNames:c,getOwnPropertySymbols:h,getPrototypeOf:u}=Object,_=globalThis,p=_.trustedTypes,g=p?p.emptyScript:"",m=_.reactiveElementPolyfillSupport,f=(t,e)=>t,v={toAttribute(t,e){switch(e){case Boolean:t=t?g:null;break;case Object:case Array:t=null==t?t:JSON.stringify(t)}return t},fromAttribute(t,e){let i=t;switch(e){case Boolean:i=null!==t;break;case Number:i=null===t?null:Number(t);break;case Object:case Array:try{i=JSON.parse(t)}catch(t){i=null}}return i}},b=(t,e)=>!a(t,e),y={attribute:!0,type:String,converter:v,reflect:!1,useDefault:!1,hasChanged:b};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */Symbol.metadata??=Symbol("metadata"),_.litPropertyMetadata??=new WeakMap;let $=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=y){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){const i=Symbol(),o=this.getPropertyDescriptor(t,i,e);void 0!==o&&l(this.prototype,t,o)}}static getPropertyDescriptor(t,e,i){const{get:o,set:n}=d(this.prototype,t)??{get(){return this[e]},set(t){this[e]=t}};return{get:o,set(e){const r=o?.call(this);n?.call(this,e),this.requestUpdate(t,r,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??y}static _$Ei(){if(this.hasOwnProperty(f("elementProperties")))return;const t=u(this);t.finalize(),void 0!==t.l&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(f("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(f("properties"))){const t=this.properties,e=[...c(t),...h(t)];for(const i of e)this.createProperty(i,t[i])}const t=this[Symbol.metadata];if(null!==t){const e=litPropertyMetadata.get(t);if(void 0!==e)for(const[t,i]of e)this.elementProperties.set(t,i)}this._$Eh=new Map;for(const[t,e]of this.elementProperties){const i=this._$Eu(t,e);void 0!==i&&this._$Eh.set(i,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){const e=[];if(Array.isArray(t)){const i=new Set(t.flat(1/0).reverse());for(const t of i)e.unshift(s(t))}else void 0!==t&&e.push(s(t));return e}static _$Eu(t,e){const i=e.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof t?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),void 0!==this.renderRoot&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){const t=new Map,e=this.constructor.elementProperties;for(const i of e.keys())this.hasOwnProperty(i)&&(t.set(i,this[i]),delete this[i]);t.size>0&&(this._$Ep=t)}createRenderRoot(){const i=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return((i,o)=>{if(e)i.adoptedStyleSheets=o.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(const e of o){const o=document.createElement("style"),n=t.litNonce;void 0!==n&&o.setAttribute("nonce",n),o.textContent=e.cssText,i.appendChild(o)}})(i,this.constructor.elementStyles),i}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,i){this._$AK(t,i)}_$ET(t,e){const i=this.constructor.elementProperties.get(t),o=this.constructor._$Eu(t,i);if(void 0!==o&&!0===i.reflect){const n=(void 0!==i.converter?.toAttribute?i.converter:v).toAttribute(e,i.type);this._$Em=t,null==n?this.removeAttribute(o):this.setAttribute(o,n),this._$Em=null}}_$AK(t,e){const i=this.constructor,o=i._$Eh.get(t);if(void 0!==o&&this._$Em!==o){const t=i.getPropertyOptions(o),n="function"==typeof t.converter?{fromAttribute:t.converter}:void 0!==t.converter?.fromAttribute?t.converter:v;this._$Em=o,this[o]=n.fromAttribute(e,t.type)??this._$Ej?.get(o)??null,this._$Em=null}}requestUpdate(t,e,i){if(void 0!==t){const o=this.constructor,n=this[t];if(i??=o.getPropertyOptions(t),!((i.hasChanged??b)(n,e)||i.useDefault&&i.reflect&&n===this._$Ej?.get(t)&&!this.hasAttribute(o._$Eu(t,i))))return;this.C(t,e,i)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(t,e,{useDefault:i,reflect:o,wrapped:n},r){i&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,r??e??this[t]),!0!==n||void 0!==r)||(this._$AL.has(t)||(this.hasUpdated||i||(e=void 0),this._$AL.set(t,e)),!0===o&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}const t=this.scheduleUpdate();return null!=t&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[t,e]of this._$Ep)this[t]=e;this._$Ep=void 0}const t=this.constructor.elementProperties;if(t.size>0)for(const[e,i]of t){const{wrapped:t}=i,o=this[e];!0!==t||this._$AL.has(e)||void 0===o||this.C(e,void 0,i,o)}}let t=!1;const e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(t=>t.hostUpdate?.()),this.update(e)):this._$EM()}catch(e){throw t=!1,this._$EM(),e}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(t){}firstUpdated(t){}};$.elementStyles=[],$.shadowRootOptions={mode:"open"},$[f("elementProperties")]=new Map,$[f("finalized")]=new Map,m?.({ReactiveElement:$}),(_.reactiveElementVersions??=[]).push("2.1.0");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const x=globalThis,w=x.trustedTypes,S=w?w.createPolicy("lit-html",{createHTML:t=>t}):void 0,C="$lit$",T=`lit$${Math.random().toFixed(9).slice(2)}$`,E="?"+T,k=`<${E}>`,A=document,P=()=>A.createComment(""),M=t=>null===t||"object"!=typeof t&&"function"!=typeof t,I=Array.isArray,V="[ \t\n\f\r]",O=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,L=/-->/g,U=/>/g,B=RegExp(`>|${V}(?:([^\\s"'>=/]+)(${V}*=${V}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),N=/'/g,D=/"/g,H=/^(?:script|style|textarea|title)$/i,R=(t=>(e,...i)=>({_$litType$:t,strings:e,values:i}))(1),j=Symbol.for("lit-noChange"),z=Symbol.for("lit-nothing"),W=new WeakMap,F=A.createTreeWalker(A,129);function q(t,e){if(!I(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==S?S.createHTML(e):e}const J=(t,e)=>{const i=t.length-1,o=[];let n,r=2===e?"<svg>":3===e?"<math>":"",s=O;for(let e=0;e<i;e++){const i=t[e];let a,l,d=-1,c=0;for(;c<i.length&&(s.lastIndex=c,l=s.exec(i),null!==l);)c=s.lastIndex,s===O?"!--"===l[1]?s=L:void 0!==l[1]?s=U:void 0!==l[2]?(H.test(l[2])&&(n=RegExp("</"+l[2],"g")),s=B):void 0!==l[3]&&(s=B):s===B?">"===l[0]?(s=n??O,d=-1):void 0===l[1]?d=-2:(d=s.lastIndex-l[2].length,a=l[1],s=void 0===l[3]?B:'"'===l[3]?D:N):s===D||s===N?s=B:s===L||s===U?s=O:(s=B,n=void 0);const h=s===B&&t[e+1].startsWith("/>")?" ":"";r+=s===O?i+k:d>=0?(o.push(a),i.slice(0,d)+C+i.slice(d)+T+h):i+T+(-2===d?e:h)}return[q(t,r+(t[i]||"<?>")+(2===e?"</svg>":3===e?"</math>":"")),o]};class G{constructor({strings:t,_$litType$:e},i){let o;this.parts=[];let n=0,r=0;const s=t.length-1,a=this.parts,[l,d]=J(t,e);if(this.el=G.createElement(l,i),F.currentNode=this.el.content,2===e||3===e){const t=this.el.content.firstChild;t.replaceWith(...t.childNodes)}for(;null!==(o=F.nextNode())&&a.length<s;){if(1===o.nodeType){if(o.hasAttributes())for(const t of o.getAttributeNames())if(t.endsWith(C)){const e=d[r++],i=o.getAttribute(t).split(T),s=/([.?@])?(.*)/.exec(e);a.push({type:1,index:n,name:s[2],strings:i,ctor:"."===s[1]?Q:"?"===s[1]?tt:"@"===s[1]?et:Z}),o.removeAttribute(t)}else t.startsWith(T)&&(a.push({type:6,index:n}),o.removeAttribute(t));if(H.test(o.tagName)){const t=o.textContent.split(T),e=t.length-1;if(e>0){o.textContent=w?w.emptyScript:"";for(let i=0;i<e;i++)o.append(t[i],P()),F.nextNode(),a.push({type:2,index:++n});o.append(t[e],P())}}}else if(8===o.nodeType)if(o.data===E)a.push({type:2,index:n});else{let t=-1;for(;-1!==(t=o.data.indexOf(T,t+1));)a.push({type:7,index:n}),t+=T.length-1}n++}}static createElement(t,e){const i=A.createElement("template");return i.innerHTML=t,i}}function K(t,e,i=t,o){if(e===j)return e;let n=void 0!==o?i._$Co?.[o]:i._$Cl;const r=M(e)?void 0:e._$litDirective$;return n?.constructor!==r&&(n?._$AO?.(!1),void 0===r?n=void 0:(n=new r(t),n._$AT(t,i,o)),void 0!==o?(i._$Co??=[])[o]=n:i._$Cl=n),void 0!==n&&(e=K(t,n._$AS(t,e.values),n,o)),e}class X{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){const{el:{content:e},parts:i}=this._$AD,o=(t?.creationScope??A).importNode(e,!0);F.currentNode=o;let n=F.nextNode(),r=0,s=0,a=i[0];for(;void 0!==a;){if(r===a.index){let e;2===a.type?e=new Y(n,n.nextSibling,this,t):1===a.type?e=new a.ctor(n,a.name,a.strings,this,t):6===a.type&&(e=new it(n,this,t)),this._$AV.push(e),a=i[++s]}r!==a?.index&&(n=F.nextNode(),r++)}return F.currentNode=A,o}p(t){let e=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(t,i,e),e+=i.strings.length-2):i._$AI(t[e])),e++}}class Y{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,i,o){this.type=2,this._$AH=z,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=i,this.options=o,this._$Cv=o?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode;const e=this._$AM;return void 0!==e&&11===t?.nodeType&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=K(this,t,e),M(t)?t===z||null==t||""===t?(this._$AH!==z&&this._$AR(),this._$AH=z):t!==this._$AH&&t!==j&&this._(t):void 0!==t._$litType$?this.$(t):void 0!==t.nodeType?this.T(t):(t=>I(t)||"function"==typeof t?.[Symbol.iterator])(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==z&&M(this._$AH)?this._$AA.nextSibling.data=t:this.T(A.createTextNode(t)),this._$AH=t}$(t){const{values:e,_$litType$:i}=t,o="number"==typeof i?this._$AC(t):(void 0===i.el&&(i.el=G.createElement(q(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===o)this._$AH.p(e);else{const t=new X(o,this),i=t.u(this.options);t.p(e),this.T(i),this._$AH=t}}_$AC(t){let e=W.get(t.strings);return void 0===e&&W.set(t.strings,e=new G(t)),e}k(t){I(this._$AH)||(this._$AH=[],this._$AR());const e=this._$AH;let i,o=0;for(const n of t)o===e.length?e.push(i=new Y(this.O(P()),this.O(P()),this,this.options)):i=e[o],i._$AI(n),o++;o<e.length&&(this._$AR(i&&i._$AB.nextSibling,o),e.length=o)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t&&t!==this._$AB;){const e=t.nextSibling;t.remove(),t=e}}setConnected(t){void 0===this._$AM&&(this._$Cv=t,this._$AP?.(t))}}class Z{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,i,o,n){this.type=1,this._$AH=z,this._$AN=void 0,this.element=t,this.name=e,this._$AM=o,this.options=n,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=z}_$AI(t,e=this,i,o){const n=this.strings;let r=!1;if(void 0===n)t=K(this,t,e,0),r=!M(t)||t!==this._$AH&&t!==j,r&&(this._$AH=t);else{const o=t;let s,a;for(t=n[0],s=0;s<n.length-1;s++)a=K(this,o[i+s],e,s),a===j&&(a=this._$AH[s]),r||=!M(a)||a!==this._$AH[s],a===z?t=z:t!==z&&(t+=(a??"")+n[s+1]),this._$AH[s]=a}r&&!o&&this.j(t)}j(t){t===z?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}}class Q extends Z{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===z?void 0:t}}class tt extends Z{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==z)}}class et extends Z{constructor(t,e,i,o,n){super(t,e,i,o,n),this.type=5}_$AI(t,e=this){if((t=K(this,t,e,0)??z)===j)return;const i=this._$AH,o=t===z&&i!==z||t.capture!==i.capture||t.once!==i.once||t.passive!==i.passive,n=t!==z&&(i===z||o);o&&this.element.removeEventListener(this.name,this,i),n&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}}class it{constructor(t,e,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){K(this,t)}}const ot=x.litHtmlPolyfillSupport;ot?.(G,Y),(x.litHtmlVersions??=[]).push("3.3.0");const nt=globalThis;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */class rt extends ${constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){const e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=((t,e,i)=>{const o=i?.renderBefore??e;let n=o._$litPart$;if(void 0===n){const t=i?.renderBefore??null;o._$litPart$=n=new Y(e.insertBefore(P(),t),t,void 0,i??{})}return n._$AI(t),n})(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return j}}rt._$litElement$=!0,rt.finalized=!0,nt.litElementHydrateSupport?.({LitElement:rt});const st=nt.litElementPolyfillSupport;st?.({LitElement:rt}),(nt.litElementVersions??=[]).push("4.2.0");const at=r`
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


  `,lt="simple_timer",dt=[15,30,60,90,120,150];console.info("%c SIMPLE-TIMER-CARD %c v1.4.2 ","color: orange; font-weight: bold; background: black","color: white; font-weight: bold; background: dimgray");customElements.define("timer-card",class extends rt{constructor(){super(...arguments),this._countdownInterval=null,this._liveRuntimeSeconds=0,this._timeRemaining=null,this._sliderValue=0,this.buttons=[],this._validationMessages=[],this._notificationSentForCurrentCycle=!1,this._entitiesLoaded=!1,this._serverTimeOffset=0,this._effectiveSwitchEntity=null,this._effectiveSensorEntity=null,this._longPressTimer=null,this._isLongPress=!1,this._touchStartPosition=null,this._isCancelling=!1}static get properties(){return{hass:{type:Object},_config:{type:Object},_timeRemaining:{state:!0},_sliderValue:{state:!0},_entitiesLoaded:{state:!0},_effectiveSwitchEntity:{state:!0},_effectiveSensorEntity:{state:!0},_validationMessages:{state:!0}}}static async getConfigElement(){return await Promise.resolve().then(function(){return pt}),document.createElement("timer-card-editor")}static getStubConfig(t){return console.log("TimerCard: Generating stub config - NO auto-selection will be performed"),{type:"custom:timer-card",timer_instance_id:null,timer_buttons:[...dt],card_title:"Simple Timer",power_button_icon:"mdi:power",hide_slider:!1,slider_thumb_color:null,slider_background_color:null,power_button_background_color:null,power_button_icon_color:null}}setConfig(t){const e=t.slider_max&&t.slider_max>0&&t.slider_max<=9999?t.slider_max:120,i=t.timer_instance_id||"default";this.buttons=this._getValidatedTimerButtons(t.timer_buttons),this._config={type:t.type||"custom:timer-card",timer_buttons:t.timer_buttons||[...dt],card_title:t.card_title||null,entity_state_icon:t.entity_state_icon||null,power_button_icon:t.power_button_icon||null,slider_max:e,slider_unit:t.slider_unit||"min",reverse_mode:t.reverse_mode||!1,hide_slider:t.hide_slider||!1,show_daily_usage:!1!==t.show_daily_usage,timer_instance_id:i,entity:t.entity,sensor_entity:t.sensor_entity,slider_thumb_color:t.slider_thumb_color||null,slider_background_color:t.slider_background_color||null,timer_button_font_color:t.timer_button_font_color||null,timer_button_background_color:t.timer_button_background_color||null,power_button_background_color:t.power_button_background_color||null,power_button_icon_color:t.power_button_icon_color||null,entity_state_button_background_color:t.entity_state_button_background_color||null,entity_state_button_icon_color:t.entity_state_button_icon_color||null,entity_state_button_background_color_on:t.entity_state_button_background_color_on||null,entity_state_button_icon_color_on:t.entity_state_button_icon_color_on||null,turn_off_on_cancel:!1!==t.turn_off_on_cancel},t.timer_instance_id&&(this._config.timer_instance_id=t.timer_instance_id),t.entity&&(this._config.entity=t.entity),t.sensor_entity&&(this._config.sensor_entity=t.sensor_entity);const o=localStorage.getItem(`simple-timer-slider-${i}`);let n=o?parseInt(o):NaN;(isNaN(n)||n<0)&&(n=e),n>e&&(n=e),this._sliderValue=n,localStorage.setItem(`simple-timer-slider-${i}`,this._sliderValue.toString()),this.requestUpdate(),this._liveRuntimeSeconds=0,this._notificationSentForCurrentCycle=!1,this._effectiveSwitchEntity=null,this._effectiveSensorEntity=null,this._entitiesLoaded=!1}_getValidatedTimerButtons(t){let e=[];if(this._validationMessages=[],Array.isArray(t)){const i=[],o=new Set,n=[];t.forEach(t=>{let r,s,a="min",l="Min";const d=String(t).trim().toLowerCase().match(/^(\d+(?:\.\d+)?)\s*(s|sec|seconds|m|min|minutes|h|hr|hours|d|day|days)?(\*)?$/);if(d){const c=parseFloat(d[1]),h=d[1].includes("."),u=d[2]||"min",_=!!d[3],p=u.startsWith("h"),g=u.startsWith("d");if(c>9999)return void i.push(t);if(h&&!p&&!g)return void i.push(t);if(h&&(p||g)){const e=d[1].split(".")[1];if(e&&e.length>1)return void i.push(t)}if(r=c,u.startsWith("s")?(a="s",l="sec",s=r/60):u.startsWith("h")?(a="h",l="hr",s=60*r):u.startsWith("d")?(a="d",l="day",s=1440*r):(a="min",l="min",s=r),r>0){const i=`${s}`;_?e.push({displayValue:r,unit:a,labelUnit:l,minutesEquivalent:s,isDefault:_}):o.has(i)?n.push(t):(o.add(i),e.push({displayValue:r,unit:a,labelUnit:l,minutesEquivalent:s,isDefault:_}))}else i.push(t)}else i.push(t)});const r=[];return i.length>0&&r.push(`Invalid timer values ignored: ${i.join(", ")}. Format example: 30, "30s", "1h", "2d". Limit 9999.`),n.length>0&&r.push("Duplicate timer values were removed."),this._validationMessages=r,e.sort((t,e)=>t.minutesEquivalent-e.minutesEquivalent),e}return null==t||(console.warn(`TimerCard: Invalid timer_buttons type (${typeof t}):`,t,"- using empty array"),this._validationMessages=[`Invalid timer_buttons configuration. Expected array, got ${typeof t}.`]),[]}_determineEffectiveEntities(){var t,e;let i=null,o=null,n=!1;if(this.hass&&this.hass.states){if(null===(t=this._config)||void 0===t?void 0:t.timer_instance_id){const t=this._config.timer_instance_id,e=Object.keys(this.hass.states).filter(t=>t.startsWith("sensor.")).find(e=>{const i=this.hass.states[e];return i.attributes.entry_id===t&&"string"==typeof i.attributes.switch_entity_id});if(e){o=e,i=this.hass.states[e].attributes.switch_entity_id,i&&this.hass.states[i]?n=!0:console.warn(`TimerCard: Configured instance '${t}' sensor '${o}' links to missing or invalid switch '${i}'.`)}else console.warn(`TimerCard: Configured timer_instance_id '${t}' does not have a corresponding simple_timer sensor found.`)}if(!n&&(null===(e=this._config)||void 0===e?void 0:e.sensor_entity)){const t=this.hass.states[this._config.sensor_entity];t&&"string"==typeof t.attributes.entry_id&&"string"==typeof t.attributes.switch_entity_id?(o=this._config.sensor_entity,i=t.attributes.switch_entity_id,i&&this.hass.states[i]?(n=!0,console.info(`TimerCard: Using manually configured sensor_entity: Sensor '${o}', Switch '${i}'.`)):console.warn(`TimerCard: Manually configured sensor '${o}' links to missing or invalid switch '${i}'.`)):console.warn(`TimerCard: Manually configured sensor_entity '${this._config.sensor_entity}' not found or missing required attributes.`)}this._effectiveSwitchEntity===i&&this._effectiveSensorEntity===o||(this._effectiveSwitchEntity=i,this._effectiveSensorEntity=o,this.requestUpdate()),this._entitiesLoaded=n}else this._entitiesLoaded=!1}_getEntryId(){if(!this._effectiveSensorEntity||!this.hass||!this.hass.states)return console.error("Timer-card: _getEntryId called without a valid effective sensor entity."),null;const t=this.hass.states[this._effectiveSensorEntity];return t&&t.attributes.entry_id?t.attributes.entry_id:(console.error("Could not determine entry_id from effective sensor_entity attributes:",this._effectiveSensorEntity),null)}_startTimer(t,e="min",i="button"){var o;if(this._validationMessages=[],!this._entitiesLoaded||!this.hass||!this.hass.callService)return void console.error("Timer-card: Cannot start timer. Entities not loaded or callService unavailable.");const n=this._getEntryId();if(!n)return void console.error("Timer-card: Entry ID not found for starting timer.");this._effectiveSwitchEntity;let r=(null===(o=this._config)||void 0===o?void 0:o.reverse_mode)||!1;if(this._effectiveSensorEntity&&this.hass){const t=this.hass.states[this._effectiveSensorEntity];t&&t.attributes.default_timer_enabled&&(r=!1)}r?this.hass.callService(lt,"start_timer",{entry_id:n,duration:t,unit:e,reverse_mode:!0,start_method:i}):this.hass.callService(lt,"start_timer",{entry_id:n,duration:t,unit:e,start_method:i}),this._notificationSentForCurrentCycle=!1}_addTimer(t,e="min"){if(this._validationMessages=[],!this._entitiesLoaded||!this.hass||!this.hass.callService)return void console.error("Timer-card: Cannot add to timer. Entities not loaded or callService unavailable.");const i=this._getEntryId();i?this.hass.callService(lt,"add_timer",{entry_id:i,duration:t,unit:e}).then(()=>{console.log(`Timer-card: Added ${t} ${e} to active timer.`)}).catch(t=>{console.error("Timer-card: Error adding to timer:",t)}):console.error("Timer-card: Entry ID not found for adding to timer.")}_cancelTimer(){var t;if(this._validationMessages=[],!this._entitiesLoaded||!this.hass||!this.hass.callService)return void console.error("Timer-card: Cannot cancel timer. Entities not loaded or callService unavailable.");this._isCancelling=!0;const e=this._getEntryId();if(!e)return console.error("Timer-card: Entry ID not found for cancelling timer."),void(this._isCancelling=!1);const i=!1!==(null===(t=this._config)||void 0===t?void 0:t.turn_off_on_cancel);this.hass.callService(lt,"cancel_timer",{entry_id:e,turn_off_entity:i}).then(()=>{setTimeout(()=>{this._isCancelling=!1},1e3)}).catch(t=>{console.error("Timer-card: Error cancelling timer:",t),this._isCancelling=!1}),this._notificationSentForCurrentCycle=!1}_handleTimerControl(){var t;if(this._validationMessages=[],!this._entitiesLoaded||!this.hass||!this.hass.states)return void console.error("Timer-card: Cannot control timer. Entities not loaded.");const e=this._effectiveSensorEntity,i=this.hass.states[e];if(!i)return void console.error("Timer-card: Sensor entity not found.");if("active"===i.attributes.timer_state)return this._cancelTimer(),void console.log("Timer-card: Stopping active timer.");if(this._sliderValue>0){const e=(null===(t=this._config)||void 0===t?void 0:t.slider_unit)||"min";this._startTimer(this._sliderValue,e,"slider"),console.log(`Timer-card: Starting timer for ${this._sliderValue} ${e}`)}else console.warn("Timer-card: Slider value is 0, cannot start timer.")}_handleIndependentPower(t){if(t.preventDefault(),t.stopPropagation(),!this._entitiesLoaded||!this.hass||!this._effectiveSwitchEntity)return void console.error("Timer-card: Cannot toggle power. Entities not loaded.");const e=this._effectiveSwitchEntity;console.log(`Timer-card: Toggling independent power for ${e}`),this.hass.callService("homeassistant","toggle",{entity_id:e}).catch(t=>console.error("Timer-card: Error toggling power:",t))}_showMoreInfo(){if(!this._entitiesLoaded||!this.hass)return void console.error("Timer-card: Cannot show more info. Entities not loaded.");const t=this._effectiveSensorEntity,e=new CustomEvent("hass-more-info",{bubbles:!0,composed:!0,detail:{entityId:t}});this.dispatchEvent(e)}connectedCallback(){var t,e;super.connectedCallback();const i=(null===(t=this._config)||void 0===t?void 0:t.timer_instance_id)||"default";if(localStorage.getItem(`simple-timer-slider-${i}`));else if(this._determineEffectiveEntities(),this._entitiesLoaded&&this.hass&&this._effectiveSensorEntity){const t=this.hass.states[this._effectiveSensorEntity],i=(null===(e=null==t?void 0:t.attributes)||void 0===e?void 0:e.timer_duration)||0;i>0&&i<=120&&(this._sliderValue=i)}this._determineEffectiveEntities(),this._updateLiveRuntime(),this._syncServerTime(),this._updateCountdown()}disconnectedCallback(){super.disconnectedCallback(),this._stopCountdown(),this._stopLiveRuntime(),this._longPressTimer&&window.clearTimeout(this._longPressTimer)}updated(t){(t.has("hass")||t.has("_config"))&&(this._determineEffectiveEntities(),this._updateLiveRuntime(),this._updateCountdown()),t.has("_config")}_updateLiveRuntime(){this._liveRuntimeSeconds=0}_stopLiveRuntime(){this._liveRuntimeSeconds=0}_updateCountdown(){if(!this._entitiesLoaded||!this.hass||!this.hass.states)return void this._stopCountdown();const t=this.hass.states[this._effectiveSensorEntity];if(!t||"active"!==t.attributes.timer_state)return this._stopCountdown(),void(this._notificationSentForCurrentCycle=!1);const e=t.attributes.timer_finishes_at;if(void 0===e)return console.warn("Timer-card: timer_finishes_at is undefined for active timer. Stopping countdown."),void this._stopCountdown();const i=new Date(e).getTime();if(this._countdownInterval&&this._currentFinishesAt!==i&&this._stopCountdown(),this._currentFinishesAt=i,!this._countdownInterval){const t=()=>{const t=(new Date).getTime()+this._serverTimeOffset,e=Math.max(0,Math.round((i-t)/1e3));if(this._getShowSeconds()){const t=Math.floor(e/3600),i=Math.floor(e%3600/60),o=e%60;this._timeRemaining=`${t.toString().padStart(2,"0")}:${i.toString().padStart(2,"0")}:${o.toString().padStart(2,"0")}`}else{const t=Math.floor(e/60),i=e%60;this._timeRemaining=`${t.toString().padStart(2,"0")}:${i.toString().padStart(2,"0")}`}0===e&&(this._stopCountdown(),this._notificationSentForCurrentCycle||(this._notificationSentForCurrentCycle=!0))};this._countdownInterval=window.setInterval(t,500),t()}}_stopCountdown(){this._countdownInterval&&(window.clearInterval(this._countdownInterval),this._countdownInterval=null),this._timeRemaining=null}_getShowSeconds(){var t;if(!this._entitiesLoaded||!this.hass||!this._effectiveSensorEntity)return!1;const e=this.hass.states[this._effectiveSensorEntity];return(null===(t=null==e?void 0:e.attributes)||void 0===t?void 0:t.show_seconds)||!1}_handleUsageClick(t){t.preventDefault(),this._isLongPress||this._showMoreInfo(),this._isLongPress=!1}_startLongPress(t){t.preventDefault(),this._isLongPress=!1,this._longPressTimer=window.setTimeout(()=>{this._isLongPress=!0,this._resetUsage(),"vibrate"in navigator&&navigator.vibrate(50)},800)}_endLongPress(t){t&&t.preventDefault(),this._longPressTimer&&(window.clearTimeout(this._longPressTimer),this._longPressTimer=null)}_handlePowerClick(t){"click"!==t.type||this._isLongPress||(t.preventDefault(),t.stopPropagation(),this._handleTimerControl()),this._isLongPress=!1}_handleTouchEnd(t){t.preventDefault(),t.stopPropagation(),this._longPressTimer&&(window.clearTimeout(this._longPressTimer),this._longPressTimer=null);let e=!1;if(this._touchStartPosition&&t.changedTouches[0]){const i=t.changedTouches[0],o=Math.abs(i.clientX-this._touchStartPosition.x),n=Math.abs(i.clientY-this._touchStartPosition.y),r=10;e=o>r||n>r}this._isLongPress||e||this._showMoreInfo(),this._isLongPress=!1,this._touchStartPosition=null}_handleTouchStart(t){t.preventDefault(),t.stopPropagation(),this._isLongPress=!1;const e=t.touches[0];this._touchStartPosition={x:e.clientX,y:e.clientY},this._longPressTimer=window.setTimeout(()=>{this._isLongPress=!0,this._resetUsage(),"vibrate"in navigator&&navigator.vibrate(50)},800)}_resetUsage(){if(this._validationMessages=[],!this._entitiesLoaded||!this.hass||!this.hass.callService)return void console.error("Timer-card: Cannot reset usage. Entities not loaded or callService unavailable.");const t=this._getEntryId();t?confirm("Reset daily usage to 00:00?\n\nThis action cannot be undone.")&&this.hass.callService(lt,"reset_daily_usage",{entry_id:t}).then(()=>{console.log("Timer-card: Daily usage reset successfully")}).catch(t=>{console.error("Timer-card: Error resetting daily usage:",t)}):console.error("Timer-card: Entry ID not found for resetting usage.")}_handleSliderChange(t){var e;const i=t.target;this._sliderValue=parseInt(i.value);const o=(null===(e=this._config)||void 0===e?void 0:e.timer_instance_id)||"default";localStorage.setItem(`simple-timer-slider-${o}`,this._sliderValue.toString())}_getCurrentTimerMode(){var t;if(!this._entitiesLoaded||!this.hass||!this._effectiveSensorEntity)return"normal";const e=this.hass.states[this._effectiveSensorEntity];return(null===(t=null==e?void 0:e.attributes)||void 0===t?void 0:t.reverse_mode)?"reverse":"normal"}_getSliderStyle(){var t,e,i;const o=(null===(t=this._config)||void 0===t?void 0:t.slider_thumb_color)||"#2ab69c",n=(null===(e=this._config)||void 0===e?void 0:e.slider_background_color)||"var(--secondary-background-color)",r=(null===(i=this._config)||void 0===i?void 0:i.slider_thumb_color)?this._adjustColorBrightness(o,20):"#4bd9bf",s=t=>{const e=/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(t);return e?{r:parseInt(e[1],16),g:parseInt(e[2],16),b:parseInt(e[3],16)}:{r:42,g:182,b:156}},a=s(o),l=s(r);return`\n      .timer-slider {\n        background: ${n} !important;\n      }\n      .timer-slider::-webkit-slider-thumb {\n        background: ${o} !important;\n        border: 2px solid ${r} !important;\n        box-shadow: \n          0 0 0 2px rgba(${l.r}, ${l.g}, ${l.b}, 0.3),\n          0 0 8px rgba(${a.r}, ${a.g}, ${a.b}, 0.4),\n          0 2px 4px rgba(0, 0, 0, 0.2) !important;\n      }\n      .timer-slider::-webkit-slider-thumb:hover {\n        background: ${this._adjustColorBrightness(o,-10)} !important;\n        border: 2px solid ${r} !important;\n        box-shadow: \n          0 0 0 3px rgba(${l.r}, ${l.g}, ${l.b}, 0.4),\n          0 0 12px rgba(${a.r}, ${a.g}, ${a.b}, 0.6),\n          0 2px 6px rgba(0, 0, 0, 0.3) !important;\n      }\n      .timer-slider::-webkit-slider-thumb:active {\n        background: ${this._adjustColorBrightness(o,-20)} !important;\n        border: 2px solid ${r} !important;\n        box-shadow: \n          0 0 0 4px rgba(${l.r}, ${l.g}, ${l.b}, 0.5),\n          0 0 16px rgba(${a.r}, ${a.g}, ${a.b}, 0.7),\n          0 2px 8px rgba(0, 0, 0, 0.4) !important;\n      }\n      .timer-slider::-moz-range-thumb {\n        background: ${o} !important;\n        border: 2px solid ${r} !important;\n        box-shadow: \n          0 0 0 2px rgba(${l.r}, ${l.g}, ${l.b}, 0.3),\n          0 0 8px rgba(${a.r}, ${a.g}, ${a.b}, 0.4),\n          0 2px 4px rgba(0, 0, 0, 0.2) !important;\n      }\n      .timer-slider::-moz-range-thumb:hover {\n        background: ${this._adjustColorBrightness(o,-10)} !important;\n        border: 2px solid ${r} !important;\n        box-shadow: \n          0 0 0 3px rgba(${l.r}, ${l.g}, ${l.b}, 0.4),\n          0 0 12px rgba(${a.r}, ${a.g}, ${a.b}, 0.6),\n          0 2px 6px rgba(0, 0, 0, 0.3) !important;\n      }\n      .timer-slider::-moz-range-thumb:active {\n        background: ${this._adjustColorBrightness(o,-20)} !important;\n        border: 2px solid ${r} !important;\n        box-shadow: \n          0 0 0 4px rgba(${l.r}, ${l.g}, ${l.b}, 0.5),\n          0 0 16px rgba(${a.r}, ${a.g}, ${a.b}, 0.7),\n          0 2px 8px rgba(0, 0, 0, 0.4) !important;\n      }\n    `}_getTimerButtonStyle(){var t,e;const i=null===(t=this._config)||void 0===t?void 0:t.timer_button_font_color,o=null===(e=this._config)||void 0===e?void 0:e.timer_button_background_color;if(!i&&!o)return"";let n="";return(i||o)&&(n+=`\n        .timer-button {\n          ${i?`color: ${i} !important;`:""}\n          ${o?`background-color: ${o} !important;`:""}\n        }\n      `),n}_getPowerButtonStyle(){var t,e,i,o,n,r;const s=null===(t=this._config)||void 0===t?void 0:t.power_button_background_color,a=null===(e=this._config)||void 0===e?void 0:e.power_button_icon_color,l=null===(i=this._config)||void 0===i?void 0:i.entity_state_button_background_color,d=null===(o=this._config)||void 0===o?void 0:o.entity_state_button_icon_color,c=null===(n=this._config)||void 0===n?void 0:n.entity_state_button_background_color_on,h=null===(r=this._config)||void 0===r?void 0:r.entity_state_button_icon_color_on;if(!(s||a||l||d||c||h))return"";let u="";return(s||a)&&(u+=`\n        .timer-control-button {\n          ${s?`background-color: ${s} !important;`:""}\n        }\n        .timer-control-button ha-icon[icon] {\n          ${a?`color: ${a} !important;`:""}\n        }\n        .timer-control-button.reverse ha-icon[icon] {\n          ${a?`color: ${a} !important;`:""}\n        }\n      `),(l||d)&&(u+=`\n        .entity-state-button {\n          ${l?`background-color: ${l} !important;`:""}\n        }\n        .entity-state-button ha-icon[icon] {\n          ${d?`color: ${d} !important;`:""}\n        }\n        .entity-state-button.reverse ha-icon[icon] {\n          ${d?`color: ${d} !important;`:""}\n        }\n      `),(c||h)&&(u+=`\n        .entity-state-button.on {\n          ${c?`background-color: ${c} !important;`:""}\n        }\n        .entity-state-button.on ha-icon[icon] {\n          ${h?`color: ${h} !important;`:""}\n        }\n        /* Ensure specific override if needed */\n        .entity-state-button.on.reverse ha-icon[icon] {\n          ${h?`color: ${h} !important;`:""}\n        }\n      `),u}_adjustColorBrightness(t,e){const i=parseInt(t.replace("#",""),16),o=Math.round(2.55*e);return"#"+(16777216+65536*Math.max(0,Math.min(255,(i>>16)+o))+256*Math.max(0,Math.min(255,(i>>8&255)+o))+Math.max(0,Math.min(255,(255&i)+o))).toString(16).slice(1)}async _fetchLovelaceConfig(){if(!this.hass)return null;try{const t=this._getDashboardUrlPath();return await this.hass.callWS({type:"lovelace/config",url_path:t})}catch(t){return console.warn("TimerCard: Failed to fetch lovelace config",t),null}}_getDashboardUrlPath(){const t=window.location.pathname.split("/");return t.length>1&&"lovelace"!==t[1]?t[1]:null}render(){var t,e,i,o,n,r,s,a,l,d,c,h;let u=null,_=!1;if(this.hass){if(!this._entitiesLoaded)if(null===(t=this._config)||void 0===t?void 0:t.timer_instance_id){const t=Object.values(this.hass.states).find(t=>t.attributes.entry_id===this._config.timer_instance_id&&t.entity_id.startsWith("sensor."));t?"string"==typeof t.attributes.switch_entity_id&&t.attributes.switch_entity_id&&this.hass.states[t.attributes.switch_entity_id]?(u="Loading Timer Control Card. Please wait...",_=!1):(u=`Timer Control Instance '${this._config.timer_instance_id}' linked to missing or invalid switch '${t.attributes.switch_entity_id}'. Please check instance configuration.`,_=!0):(u="Please select a valid instance in the card editor.",_=!0)}else if(null===(e=this._config)||void 0===e?void 0:e.sensor_entity){const t=this.hass.states[this._config.sensor_entity];t?"string"==typeof t.attributes.switch_entity_id&&t.attributes.switch_entity_id&&this.hass.states[t.attributes.switch_entity_id]?(u="Loading Timer Control Card. Please wait...",_=!1):(u=`Configured Timer Control Sensor '${this._config.sensor_entity}' is invalid or its linked switch '${t.attributes.switch_entity_id}' is missing. Please select a valid instance.`,_=!0):(u=`Configured Timer Control Sensor '${this._config.sensor_entity}' not found. Please select a valid instance in the card editor.`,_=!0)}else u="Select a Timer Control Instance from the dropdown in the card editor to link this card.",_=!1}else u="Home Assistant object (hass) not available. Card cannot load.",_=!0;if(u)return R`<ha-card><div class="${_?"warning":"placeholder"}">${u}</div></ha-card>`;const p=this.hass.states[this._effectiveSwitchEntity],g=this.hass.states[this._effectiveSensorEntity],m="on"===p.state,f="active"===g.attributes.timer_state,v=g.attributes.timer_duration||0,b=g.attributes.reverse_mode,y=parseFloat(g.state)||0;let $,x;if(this._getShowSeconds()){const t=Math.floor(y),e=Math.floor(t/3600),i=Math.floor(t%3600/60),o=t%60;$=`Daily usage: ${e.toString().padStart(2,"0")}:${i.toString().padStart(2,"0")}:${o.toString().padStart(2,"0")}`,x=this._timeRemaining||"00:00:00"}else{const t=Math.floor(y/60),e=t%60;$=`Daily usage: ${Math.floor(t/60).toString().padStart(2,"0")}:${e.toString().padStart(2,"0")}`,x=this._timeRemaining||"00:00"}const w=g.attributes.watchdog_message;return R`
      <style>
        ${this._getSliderStyle()}
        ${this._getTimerButtonStyle()}
        ${this._getPowerButtonStyle()}
      </style>
      <ha-card>
        <div class="card-header ${(null===(i=this._config)||void 0===i?void 0:i.card_title)?"has-title":""}">
						<div class="card-title">${(null===(o=this._config)||void 0===o?void 0:o.card_title)||""}</div>
				</div>

        ${w?R`
          <div class="status-message warning watchdog-banner">
            <ha-icon icon="mdi:alert-outline" class="status-icon"></ha-icon>
            <span class="status-text">${w}</span>
          </div>
        `:""}


        <div class="card-content">

          
          <!-- Independent Power Toggle (Always Visible now) -->
          <div class="entity-state-button ${m?"on":""}"
                @click=${this._handleIndependentPower}
                title="Toggle Power (Independent)">
            <ha-icon icon="${(null===(n=this._config)||void 0===n?void 0:n.entity_state_icon)||(null===(r=this._config)||void 0===r?void 0:r.power_button_icon)||"mdi:power"}"></ha-icon>
          </div>
          
          ${""}

          <!-- Countdown Display Section -->
          <div class="countdown-section">
            <div class="countdown-display ${f?"active":""} ${b?"reverse":""}">
              ${x}
            </div>
						${!1!==(null===(s=this._config)||void 0===s?void 0:s.show_daily_usage)?R`
							<div class="daily-usage-display"
									 @click=${this._handleUsageClick}
									 @mousedown=${this._startLongPress}
									 @mouseup=${this._endLongPress}
									 @mouseleave=${this._endLongPress}
									 @touchstart=${this._handleTouchStart}
									 @touchend=${this._handleTouchEnd}
									 @touchcancel=${this._endLongPress}
									 title="Click to show more info, hold to reset daily usage">
								${$}
            </div>
						`:""}
          </div>

          <!-- Slider Row -->
          ${(null===(a=this._config)||void 0===a?void 0:a.hide_slider)?"":R`
          <div class="slider-row">
            <input
              type="range"
              min="0"
              step="1"
              max="${(null===(l=this._config)||void 0===l?void 0:l.slider_max)||120}"
              .value=${this._sliderValue.toString()}
              @input=${this._handleSliderChange}
              class="timer-slider"
            />
            
            <div class="slider-right-group">
                <span class="slider-label">${this._sliderValue} ${(null===(d=this._config)||void 0===d?void 0:d.slider_unit)||"min"}</span>
                
                <div class="timer-control-button ${f?"active":""} ${f||0!==this._sliderValue?"":"disabled"}" 
                     @click=${f||0!==this._sliderValue?this._handleTimerControl:null}
                     title="${f?"Stop Timer":0===this._sliderValue?"Set time to start":"Start Timer"}">
                  <ha-icon icon="${f||0===this._sliderValue?"mdi:stop":"mdi:play"}"></ha-icon>
                </div>
            </div>
          </div>
          `}

          </div>
          
           <!-- Timer Buttons Grid -->
           ${this.buttons.length>0||(null===(c=this._config)||void 0===c?void 0:c.hide_slider)&&f?R`
          <div class="button-grid">
            ${this.buttons.map(t=>{if(t.isDefault)return"";const e=f&&Math.abs(v-t.minutesEquivalent)<.001&&"button"===g.attributes.timer_start_method;return R`
                <div class="timer-button ${e?"active":""}" 
                     @click=${()=>{f?this._addTimer(t.displayValue,t.unit):this._startTimer(t.displayValue,t.unit,"button")}}>
                  <div class="timer-button-value">${f?"+":""}${t.displayValue}</div>
                  <div class="timer-button-unit">${t.labelUnit}</div>
                </div>
              `})}
            
            ${(null===(h=this._config)||void 0===h?void 0:h.hide_slider)?R`
                <!-- Stop Button appended to grid when slider is hidden -->
                <div class="timer-button stop-button ${f?"active":"disabled"}" 
                     style="color: var(--primary-color);"
                     @click=${f?this._handleTimerControl:null}>
                  <div class="timer-button-value">
                    <ha-icon icon="mdi:stop"></ha-icon>
                  </div>
                  <div class="timer-button-unit">Stop</div>
                </div>
            `:""}
          </div>
          `:""}
        </div>

        ${this._validationMessages.length>0?R`
          <div class="status-message warning">
            <ha-icon icon="mdi:alert-outline" class="status-icon"></ha-icon>
            <div class="status-text">
                ${this._validationMessages.map(t=>R`<div>${t}</div>`)}
            </div>
          </div>
        `:""}
      </ha-card>
    `}static get styles(){return at}async _syncServerTime(){if(this.hass)try{const t=await this.hass.callApi("POST","template",{template:"{{ now().timestamp() }}"}),e=parseFloat(t);if(!isNaN(e)){const t=1e3*e,i=(new Date).getTime();this._serverTimeOffset=t-i}}catch(t){console.warn("TimerCard: Failed to sync server time",t)}}}),window.customCards=window.customCards||[],window.customCards.push({type:"timer-card",name:"Simple Timer Card",description:"A card for the Simple Timer integration."});const ct=r`
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
`,ht="instance_title",ut=[15,30,60,90,120,150];class _t extends rt{constructor(){super(),this._configFullyLoaded=!1,this._timerInstancesOptions=[],this._tempSliderMaxValue=null,this._newTimerButtonValue="",this._config={type:"custom:timer-card",timer_buttons:[...ut],timer_instance_id:null,card_title:null}}_getComputedCSSVariable(t,e="#000000"){try{const e=getComputedStyle(document.documentElement).getPropertyValue(t).trim();if(e&&""!==e)return e}catch(e){console.warn(`Failed to get CSS variable ${t}:`,e)}return e}_rgbToHex(t){const e=t.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)/);if(e){return"#"+((1<<24)+(parseInt(e[1])<<16)+(parseInt(e[2])<<8)+parseInt(e[3])).toString(16).slice(1)}return t}_getThemeColorHex(t,e="#000000"){const i=this._getComputedCSSVariable(t,e);return i.startsWith("#")?i:i.startsWith("rgb")?this._rgbToHex(i):e}async _getSimpleTimerInstances(){if(!this.hass||!this.hass.states)return console.warn("TimerCardEditor: hass.states not available when trying to fetch instances from states."),[];const t=new Map;for(const e in this.hass.states){const i=this.hass.states[e];if(e.startsWith("sensor.")&&e.includes("runtime")&&i.attributes.entry_id&&"string"==typeof i.attributes.entry_id&&i.attributes.switch_entity_id&&"string"==typeof i.attributes.switch_entity_id){const o=i.attributes.entry_id,n=i.attributes[ht];let r=`Timer Control (${o.substring(0,8)})`;console.debug(`TimerCardEditor: Processing sensor ${e} (Entry: ${o})`),console.debug(`TimerCardEditor: Found raw attribute '${ht}': ${n}`),console.debug("TimerCardEditor: Type of raw attribute: "+typeof n),n&&"string"==typeof n&&""!==n.trim()?(r=n.trim(),console.debug(`TimerCardEditor: Using '${ht}' for label: "${r}"`)):console.warn(`TimerCardEditor: Sensor '${e}' has no valid '${ht}' attribute. Falling back to entry ID based label: "${r}".`),t.has(o)?console.debug(`TimerCardEditor: Skipping duplicate entry_id: ${o}`):(t.set(o,{value:o,label:r}),console.debug(`TimerCardEditor: Added instance: ${r} (${o}) from sensor: ${e}`))}}const e=Array.from(t.values());return e.sort((t,e)=>t.label.localeCompare(e.label)),0===e.length&&console.info("TimerCardEditor: No Simple Timer integration instances found by scanning hass.states."),e}_getValidatedTimerButtons(t){if(Array.isArray(t)){const e=[],i=new Set;t.forEach(t=>{let o=String(t).trim().toLowerCase();o.endsWith("*")&&(o=o.slice(0,-1));const n=o.match(/^(\d+(?:\.\d+)?)\s*(s|sec|seconds|m|min|minutes|h|hr|hours|d|day|days)?$/);if(n){const r=parseFloat(n[1]),s=n[1].includes("."),a=n[2]||"min",l=a.startsWith("h")||["h","hr","hours"].includes(a),d=a.startsWith("d")||["d","day","days"].includes(a);if(s&&!l&&!d)return;if(s&&(l||d)){const t=n[1].split(".")[1];if(t&&t.length>1)return}if(r>9999)return;["m","min","minutes"].includes(a)?r>0&&r<=9999&&(i.has(String(r))||(e.push(r),i.add(String(r)))):i.has(o)||(e.push(t.toString().replace("*","")),i.add(o))}});const o=e.filter(t=>"number"==typeof t),n=e.filter(t=>"string"==typeof t);return o.sort((t,e)=>t-e),n.sort(),[...o,...n]}return null==t?(console.log("TimerCardEditor: No timer_buttons in config, using empty array."),[]):(console.warn(`TimerCardEditor: Invalid timer_buttons type (${typeof t}):`,t,"- using empty array"),[])}async setConfig(t){const e=Object.assign({},this._config),i=this._getValidatedTimerButtons(t.timer_buttons),o={type:t.type||"custom:timer-card",timer_buttons:i,card_title:t.card_title||null,entity_state_icon:t.entity_state_icon||t.power_button_icon||null,slider_max:t.slider_max||120,slider_unit:t.slider_unit||"min",reverse_mode:t.reverse_mode||!1,hide_slider:t.hide_slider||!1,show_daily_usage:!1!==t.show_daily_usage,slider_thumb_color:t.slider_thumb_color||null,slider_background_color:t.slider_background_color||null,timer_button_font_color:t.timer_button_font_color||null,timer_button_background_color:t.timer_button_background_color||null,power_button_background_color:t.power_button_background_color||null,power_button_icon_color:t.power_button_icon_color||null,entity_state_button_background_color:t.entity_state_button_background_color||null,entity_state_button_icon_color:t.entity_state_button_icon_color||null,entity_state_button_background_color_on:t.entity_state_button_background_color_on||null,entity_state_button_icon_color_on:t.entity_state_button_icon_color_on||null,turn_off_on_cancel:!1!==t.turn_off_on_cancel};t.timer_instance_id?o.timer_instance_id=t.timer_instance_id:console.info("TimerCardEditor: setConfig - no timer_instance_id in config, will remain unset"),t.entity&&(o.entity=t.entity),t.sensor_entity&&(o.sensor_entity=t.sensor_entity),this._config=o,this._configFullyLoaded=!0,JSON.stringify(e)!==JSON.stringify(this._config)?this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:this._config}})):console.log("TimerCardEditor: Config unchanged, not dispatching event"),this.requestUpdate()}connectedCallback(){super.connectedCallback(),this.hass?this._fetchTimerInstances():console.warn("TimerCardEditor: hass not available on connectedCallback. Deferring instance fetch.")}updated(t){var e;super.updated(t),t.has("hass")&&this.hass&&((null===(e=t.get("hass"))||void 0===e?void 0:e.states)===this.hass.states&&0!==this._timerInstancesOptions.length||this._fetchTimerInstances())}async _fetchTimerInstances(){var t;if(this.hass){if(this._timerInstancesOptions=await this._getSimpleTimerInstances(),(null===(t=this._config)||void 0===t?void 0:t.timer_instance_id)&&this._timerInstancesOptions.length>0){if(!this._timerInstancesOptions.some(t=>t.value===this._config.timer_instance_id)){console.warn(`TimerCardEditor: Previously configured instance '${this._config.timer_instance_id}' no longer exists. User will need to select a new instance.`);const t=Object.assign(Object.assign({},this._config),{timer_instance_id:null});this._config=t,this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:this._config},bubbles:!0,composed:!0}))}}else console.info("TimerCardEditor: No timer_instance_id configured or no instances available. User must manually select.");this.requestUpdate()}}_handleNewTimerInput(t){const e=t.target;this._newTimerButtonValue=e.value}_addTimerButton(){var t;const e=this._newTimerButtonValue.trim();if(!e)return;const i=e.match(/^(\d+(?:\.\d+)?)\s*(s|sec|seconds|m|min|minutes|h|hr|hours|d|day|days)?$/i);if(!i)return void alert("Invalid format! Use format like: 30, 30s, 10m, 1.5h, 1d.");const o=parseFloat(i[1]),n=i[1].includes("."),r=(i[2]||"min").toLowerCase(),s=r.startsWith("h"),a=r.startsWith("d");if(o>9999)return void alert("Value cannot exceed 9999");if(n&&!s&&!a)return void alert("Fractional values are only allowed for Hours (h) and Days (d)");if(n&&(s||a)){const t=i[1].split(".")[1];if(t&&t.length>1)return void alert("Maximum 1 decimal place allowed (e.g. 1.5)")}let l=o;if(r.startsWith("s")?l=o/60:r.startsWith("h")?l=60*o:r.startsWith("d")&&(l=1440*o),l<=0)return void alert("Timer duration must be greater than 0");let d=Array.isArray(null===(t=this._config)||void 0===t?void 0:t.timer_buttons)?[...this._config.timer_buttons]:[],c=e;if(i[2]||(c=o),d.includes(c))return this._newTimerButtonValue="",void this.requestUpdate();d.push(c);const h=d.filter(t=>"number"==typeof t),u=d.filter(t=>"string"==typeof t);h.sort((t,e)=>t-e),u.sort((t,e)=>t.localeCompare(e,void 0,{numeric:!0,sensitivity:"base"})),d=[...h,...u],this._updateConfig({timer_buttons:d}),this._newTimerButtonValue="",this.requestUpdate()}_removeTimerButton(t){var e;let i=Array.isArray(null===(e=this._config)||void 0===e?void 0:e.timer_buttons)?[...this._config.timer_buttons]:[];i=i.filter(e=>e!==t),this._updateConfig({timer_buttons:i})}_updateConfig(t){const e=Object.assign(Object.assign({},this._config),t);this._config=e,this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:this._config},bubbles:!0,composed:!0})),this.requestUpdate()}render(){var t,e,i,o,n,r,s,a,l,d,c,h,u,_,p,g,m,f,v,b,y,$,x,w,S,C,T,E,k,A,P,M,I,V,O,L;if(!this.hass)return R``;const U=this._timerInstancesOptions||[],B=[{value:"",label:"None"}],N=null!==(t=this._tempSliderMaxValue)&&void 0!==t?t:String(null!==(e=this._config.slider_max)&&void 0!==e?e:120);U.length>0?B.push(...U):B.push({value:"none_found",label:"No Simple Timer Instances Found"});let D=!1,H="";if((null===(i=this._config)||void 0===i?void 0:i.timer_instance_id)&&this.hass&&this.hass.states){const t=Object.values(this.hass.states).find(t=>t.entity_id.startsWith("sensor.")&&t.attributes.entry_id===this._config.timer_instance_id);if(t&&t.attributes.default_timer_enabled){D=!0;H=`(${t.attributes.default_timer_duration}${t.attributes.default_timer_unit||"min"})`}}const j=this._getThemeColorHex("--secondary-background-color","#424242"),z=this._getThemeColorHex("--primary-text-color","#ffffff"),W=this._getThemeColorHex("--secondary-background-color","#424242"),F=this._getThemeColorHex("--secondary-background-color","#424242"),q=this._getThemeColorHex("--primary-color","#03a9f4"),J=this._getThemeColorHex("--ha-card-background",this._getThemeColorHex("--card-background-color","#1c1c1c")),G=this._getThemeColorHex("--secondary-text-color","#727272"),K=this._getThemeColorHex("--ha-card-background",this._getThemeColorHex("--card-background-color","#1c1c1c")),X=this._getThemeColorHex("--primary-color","#03a9f4");return R`
      <div class="card-config">
        <div class="config-row">
          <ha-textfield
            .label=${"Card Title (optional)"}
            .value=${(null===(o=this._config)||void 0===o?void 0:o.card_title)||""}
            .configValue=${"card_title"}
            @input=${this._valueChanged}
            .placeholder=${"Optional title for the card"}
          ></ha-textfield>
        </div>
        
        <div class="config-row">
          <ha-select
            .label=${"Select Simple Timer Instance"}
            .value=${(null===(n=this._config)||void 0===n?void 0:n.timer_instance_id)||""}
            .configValue=${"timer_instance_id"}
            @selected=${this._valueChanged}
            @closed=${t=>t.stopPropagation()}
            fixedMenuPosition
            naturalMenuWidth
            required
          >
            ${B.map(t=>R`
              <mwc-list-item .value=${t.value}>
                ${t.label}
              </mwc-list-item>
            `)}
          </ha-select>
        </div>
        
        <div class="config-row">
          <ha-textfield
            .label=${"Entity State Icon (optional)"}
            .value=${(null===(r=this._config)||void 0===r?void 0:r.entity_state_icon)||""}
            .configValue=${"entity_state_icon"}
            @input=${this._valueChanged}
            .placeholder=${"e.g., mdi:power, mdi:lightbulb, or leave empty for no icon"}
            .helper=${"Enter any MDI icon name (mdi:icon-name) or leave empty to default to mdi:power"}
          >
            ${(null===(s=this._config)||void 0===s?void 0:s.entity_state_icon)?R`
              <ha-icon icon="${this._config.entity_state_icon}" slot="leadingIcon"></ha-icon>
            `:""}
          </ha-textfield>
        </div>


        
        <div class="config-row">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
             <ha-textfield
              label="Slider maximum (1–9999)"
              type="number"
              min="1"
              max="9999"
              inputmode="numeric"
              value=${N}
              helper="Enter a number between 1 and 9999"
              validationMessage="Must be 1–9999"
              ?invalid=${this._isSliderMaxInvalid()}
              @input=${this._onSliderMaxInput}
              @change=${this._handleSliderMaxBlur}
              @blur=${this._handleSliderMaxBlur}
              @keydown=${t=>{"Enter"===t.key&&this._handleSliderMaxBlur(t)}}
            ></ha-textfield>

            <ha-select
              .label=${"Slider Unit"}
              .value=${(null===(a=this._config)||void 0===a?void 0:a.slider_unit)||"min"}
              .configValue=${"slider_unit"}
              @selected=${this._valueChanged}
              @closed=${t=>t.stopPropagation()}
              fixedMenuPosition
              naturalMenuWidth
            >
              <mwc-list-item value="sec">Seconds (s)</mwc-list-item>
              <mwc-list-item value="min">Minutes (m)</mwc-list-item>
              <mwc-list-item value="hr">Hours (h)</mwc-list-item>
              <mwc-list-item value="day">Days (d)</mwc-list-item>
            </ha-select>
          </div>
        </div>

        <ha-expansion-panel outlined style="margin-top: 16px; margin-bottom: 16px;">
          <div slot="header" style="display: flex; align-items: center;">
            <ha-icon icon="mdi:palette-outline" style="margin-right: 8px;"></ha-icon>
            Appearance
          </div>
          <div class="content" style="padding: 12px; margin-top: 12px;">
            <div class="config-row">
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <!-- Slider Thumb Color -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${(null===(l=this._config)||void 0===l?void 0:l.slider_thumb_color)||"#2ab69c"}
                    @input=${t=>{const e=t.target;this._valueChanged({target:{configValue:"slider_thumb_color",value:e.value},stopPropagation:()=>{}})}}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"Slider Thumb Color"}
                    .value=${(null===(d=this._config)||void 0===d?void 0:d.slider_thumb_color)||""}
                    .configValue=${"slider_thumb_color"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Leave empty to use default (#2ab69c)"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>
                
                <!-- Slider Background Color -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${(null===(c=this._config)||void 0===c?void 0:c.slider_background_color)||j}
                    @input=${t=>{const e=t.target;this._valueChanged({target:{configValue:"slider_background_color",value:e.value},stopPropagation:()=>{}})}}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"Slider Background Color"}
                    .value=${(null===(h=this._config)||void 0===h?void 0:h.slider_background_color)||""}
                    .configValue=${"slider_background_color"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Leave empty to use theme color"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>
              </div>
            </div>
            
            <div class="config-row">
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <!-- Timer Button Font Color -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${(null===(u=this._config)||void 0===u?void 0:u.timer_button_font_color)||z}
                    @input=${t=>{const e=t.target;this._valueChanged({target:{configValue:"timer_button_font_color",value:e.value},stopPropagation:()=>{}})}}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"Timer Button Font Color"}
                    .value=${(null===(_=this._config)||void 0===_?void 0:_.timer_button_font_color)||""}
                    .configValue=${"timer_button_font_color"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Leave empty to use theme color"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>
                
                <!-- Timer Button Background Color -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${(null===(p=this._config)||void 0===p?void 0:p.timer_button_background_color)||W}
                    @input=${t=>{const e=t.target;this._valueChanged({target:{configValue:"timer_button_background_color",value:e.value},stopPropagation:()=>{}})}}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"Timer Button Background Color"}
                    .value=${(null===(g=this._config)||void 0===g?void 0:g.timer_button_background_color)||""}
                    .configValue=${"timer_button_background_color"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Leave empty to use theme color"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>
              </div>
            </div>
            
            <div class="config-row">
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <!-- Timer Control Button Background Color -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${(null===(m=this._config)||void 0===m?void 0:m.power_button_background_color)||F}
                    @input=${t=>{const e=t.target;this._valueChanged({target:{configValue:"power_button_background_color",value:e.value},stopPropagation:()=>{}})}}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"Timer Control Button Background"}
                    .value=${(null===(f=this._config)||void 0===f?void 0:f.power_button_background_color)||""}
                    .configValue=${"power_button_background_color"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Button next to slider"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>
                
                <!-- Timer Control Button Icon Color -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${(null===(v=this._config)||void 0===v?void 0:v.power_button_icon_color)||q}
                    @input=${t=>{const e=t.target;this._valueChanged({target:{configValue:"power_button_icon_color",value:e.value},stopPropagation:()=>{}})}}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"Timer Control Button Icon Color"}
                    .value=${(null===(b=this._config)||void 0===b?void 0:b.power_button_icon_color)||""}
                    .configValue=${"power_button_icon_color"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Button next to slider"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>
              </div>
            </div>
            
            <!-- NEW: Entity State Button Colors -->
            <div class="config-row">
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <!-- Entity State Button Background Color -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${(null===(y=this._config)||void 0===y?void 0:y.entity_state_button_background_color)||J}
                    @input=${t=>{const e=t.target;this._valueChanged({target:{configValue:"entity_state_button_background_color",value:e.value},stopPropagation:()=>{}})}}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"State Icon Background (Off)"}
                    .value=${(null===($=this._config)||void 0===$?void 0:$.entity_state_button_background_color)||""}
                    .configValue=${"entity_state_button_background_color"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default (Transparent)"}
                    .helper=${"Leave empty to use theme color"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>
                
                
                <!-- Entity State Button Icon Color -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${(null===(x=this._config)||void 0===x?void 0:x.entity_state_button_icon_color)||G}
                    @input=${t=>{const e=t.target;this._valueChanged({target:{configValue:"entity_state_button_icon_color",value:e.value},stopPropagation:()=>{}})}}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"State Icon Color (Off)"}
                    .value=${(null===(w=this._config)||void 0===w?void 0:w.entity_state_button_icon_color)||""}
                    .configValue=${"entity_state_button_icon_color"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Leave empty to use theme color"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>

                <!-- Entity State Button Background Color (On) -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${(null===(S=this._config)||void 0===S?void 0:S.entity_state_button_background_color_on)||K}
                    @input=${t=>{const e=t.target;this._valueChanged({target:{configValue:"entity_state_button_background_color_on",value:e.value},stopPropagation:()=>{}})}}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"State Icon Background (On)"}
                    .value=${(null===(C=this._config)||void 0===C?void 0:C.entity_state_button_background_color_on)||""}
                    .configValue=${"entity_state_button_background_color_on"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Leave empty to use theme color"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>

                <!-- Entity State Button Icon Color (On) -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${(null===(T=this._config)||void 0===T?void 0:T.entity_state_button_icon_color_on)||X}
                    @input=${t=>{const e=t.target;this._valueChanged({target:{configValue:"entity_state_button_icon_color_on",value:e.value},stopPropagation:()=>{}})}}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"State Icon Color (On)"}
                    .value=${(null===(E=this._config)||void 0===E?void 0:E.entity_state_button_icon_color_on)||""}
                    .configValue=${"entity_state_button_icon_color_on"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Leave empty to use theme color"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>
              </div>
            </div>
          </div>
        </ha-expansion-panel>
        
        <div class="config-row">
          <ha-formfield .label=${"Turn off entity on timer cancel"}>
            <ha-switch
              .checked=${!1!==(null===(k=this._config)||void 0===k?void 0:k.turn_off_on_cancel)}
              .configValue=${"turn_off_on_cancel"}
              @change=${this._valueChanged}
            ></ha-switch>
          </ha-formfield>
        </div>



        <div class="config-row">
          <ha-formfield .label=${"Reverse Mode (Delayed Start)"+(D?" (Disabled)":"")}>
            <ha-switch
              .checked=${!!(null===(A=this._config)||void 0===A?void 0:A.reverse_mode)&&!D}
              .configValue=${"reverse_mode"}
              @change=${this._valueChanged}
              .disabled=${D}
            ></ha-switch>
          </ha-formfield>
          ${D?R`
            <div class="helper-text" style="color: var(--warning-color, orange); margin-top: 4px;">
              Disabled because a 
              <span 
                @click=${t=>this._navigate(t,"/config/integrations/integration/simple_timer")} 
                style="color: inherit; text-decoration: underline; font-weight: bold; cursor: pointer;">
                Default Timer
              </span>
              is configured ${H}.
            </div>
          `:""}
        </div>
        
        <div class="config-row">
          <ha-formfield .label=${"Hide Timer Slider"}>
            <ha-switch
              .checked=${(null===(P=this._config)||void 0===P?void 0:P.hide_slider)||!1}
              .configValue=${"hide_slider"}
              @change=${this._valueChanged}
            ></ha-switch>
          </ha-formfield>
        </div>
        
        <div class="config-row">
          <ha-formfield .label=${"Show Daily Usage"}>
            <ha-switch
              .checked=${!1!==(null===(M=this._config)||void 0===M?void 0:M.show_daily_usage)}
              .configValue=${"show_daily_usage"}
              @change=${this._valueChanged}
            ></ha-switch>
          </ha-formfield>
        </div>
        
      </div>

        <div class="config-row">
            <div class="timer-chips-container">
             <label class="config-label">Timer Presets</label>
             <div class="chips-wrapper">
                ${((null===(I=this._config)||void 0===I?void 0:I.timer_buttons)||ut).map(t=>{const e=String(t).replace("*","");return R`
                    <div class="timer-chip">
                        <span>${"number"==typeof t?t+"m":e}</span>
                        <span class="remove-chip" @click=${()=>this._removeTimerButton(t)}>✕</span>
                    </div>
                `})}
             </div>
            </div>
            
            <div class="add-timer-row">
               <ha-textfield
                  .label=${"Add Timer (e.g. 30s, 10m, 1h)"}
                  .value=${this._newTimerButtonValue}
                  @input=${this._handleNewTimerInput}
                  @keypress=${t=>{"Enter"===t.key&&this._addTimerButton()}}
                  style="flex: 1;"
               ></ha-textfield>
               <div class="add-btn" @click=${this._addTimerButton} role="button">ADD</div>
            </div>
            <div class="helper-text" style="font-size: 0.8em; color: var(--secondary-text-color); margin-top: 4px;">
                Supports seconds (s), minutes (m), hours (h), days (d). Example: 30s, 10, 1.5h, 1d.
            </div>
        </div>
          ${!(null===(O=null===(V=this._config)||void 0===V?void 0:V.timer_buttons)||void 0===O?void 0:O.length)&&(null===(L=this._config)||void 0===L?void 0:L.hide_slider)?R`
            <p class="info-text">ℹ️ No timer presets logic and the Slider is also hidden. The card will not be able to set a duration.</p>
          `:""}
        </div>
      </div>
    `}_onSliderMaxInput(t){const e=t.currentTarget;this._tempSliderMaxValue=e.value,this.requestUpdate()}_isSliderMaxInvalid(){var t,e;const i=null!==(t=this._tempSliderMaxValue)&&void 0!==t?t:String(null!==(e=this._config.slider_max)&&void 0!==e?e:"");if(""===i)return!0;const o=Number(i);return!Number.isFinite(o)||!(o>=1&&o<=9999)}_valueChanged(t){t.stopPropagation();const e=t.target;if(!this._config||!e.configValue)return;const i=e.configValue;let o;if(void 0!==e.checked)o=e.checked;else if(void 0!==e.selected)o=e.value;else{if(void 0===e.value)return;o=e.value}const n=Object.assign({},this._config);if("card_title"===i?o&&""!==o?n.card_title=o:delete n.card_title:"timer_instance_id"===i?n.timer_instance_id=o&&"none_found"!==o&&""!==o?o:null:"show_daily_usage"===i?n.show_daily_usage=o:"hide_slider"===i?n.hide_slider=o:"reverse_mode"===i?n.reverse_mode=o:"slider_unit"===i?n.slider_unit=o:"turn_off_on_cancel"===i?n.turn_off_on_cancel=o:o&&""!==o?n[i]=o:["entity_state_icon","power_button_icon","slider_thumb_color","slider_background_color","timer_button_font_color","timer_button_background_color","power_button_background_color","power_button_icon_color","entity_state_button_background_color","entity_state_button_icon_color","entity_state_button_background_color_on","entity_state_button_icon_color_on"].includes(i)?n[i]=null:delete n[i],JSON.stringify(this._config)!==JSON.stringify(n)){this._config=n;const t=Object.assign({},n);delete t.notification_entity,delete t.show_seconds,this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:t},bubbles:!0,composed:!0})),this.requestUpdate()}}_handleSliderMaxBlur(t){var e;const i=t.currentTarget,o=(null!==(e=i.value)&&void 0!==e?e:"").trim(),n=Number(o),r=!o||!Number.isFinite(n)||n<1||n>9999?120:Math.trunc(n);i.value=String(r),this._tempSliderMaxValue=null;let s=[...this._config.timer_buttons||[]];s=s.filter(t=>"number"!=typeof t||t<=r);const a=Object.assign(Object.assign({},this._config),{slider_max:r,timer_buttons:s});this._config=a,this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:a},bubbles:!0,composed:!0})),this.requestUpdate()}_navigate(t,e){t.stopPropagation(),t.preventDefault(),this.dispatchEvent(new CustomEvent("close-dialog",{bubbles:!0,composed:!0}));try{let t=this;for(;t;){if("HA-DIALOG"===t.tagName||"MWC-DIALOG"===t.tagName){"function"==typeof t.close&&t.close();break}if(t.parentNode)t=t.parentNode;else{if(!t.host)break;t=t.host}}}catch(t){console.warn("TimerCardEditor: Failed to force close dialog",t)}history.pushState(null,"",e);const i=new Event("location-changed",{bubbles:!0,composed:!0});window.dispatchEvent(i)}static get styles(){return ct}}_t.properties={hass:{type:Object},_config:{type:Object},_newTimerButtonValue:{type:String}},customElements.define("timer-card-editor",_t);var pt=Object.freeze({__proto__:null});
//# sourceMappingURL=timer-card.js.map
