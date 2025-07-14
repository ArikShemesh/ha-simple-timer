/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const t=globalThis,e=t.ShadowRoot&&(void 0===t.ShadyCSS||t.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,i=Symbol(),s=new WeakMap;let n=class{constructor(t,e,s){if(this._$cssResult$=!0,s!==i)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o;const i=this.t;if(e&&void 0===t){const e=void 0!==i&&1===i.length;e&&(t=s.get(i)),void 0===t&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),e&&s.set(i,t))}return t}toString(){return this.cssText}};const o=(t,...e)=>{const s=1===t.length?t[0]:e.reduce((e,i,s)=>e+(t=>{if(!0===t._$cssResult$)return t.cssText;if("number"==typeof t)return t;throw Error("Value passed to 'css' function must be a 'css' function result: "+t+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+t[s+1],t[0]);return new n(s,t,i)},r=e?t=>t:t=>t instanceof CSSStyleSheet?(t=>{let e="";for(const i of t.cssRules)e+=i.cssText;return(t=>new n("string"==typeof t?t:t+"",void 0,i))(e)})(t):t,{is:a,defineProperty:c,getOwnPropertyDescriptor:l,getOwnPropertyNames:d,getOwnPropertySymbols:h,getPrototypeOf:u}=Object,_=globalThis,f=_.trustedTypes,g=f?f.emptyScript:"",p=_.reactiveElementPolyfillSupport,m=(t,e)=>t,v={toAttribute(t,e){switch(e){case Boolean:t=t?g:null;break;case Object:case Array:t=null==t?t:JSON.stringify(t)}return t},fromAttribute(t,e){let i=t;switch(e){case Boolean:i=null!==t;break;case Number:i=null===t?null:Number(t);break;case Object:case Array:try{i=JSON.parse(t)}catch(t){i=null}}return i}},y=(t,e)=>!a(t,e),b={attribute:!0,type:String,converter:v,reflect:!1,useDefault:!1,hasChanged:y};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */Symbol.metadata??=Symbol("metadata"),_.litPropertyMetadata??=new WeakMap;let $=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=b){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){const i=Symbol(),s=this.getPropertyDescriptor(t,i,e);void 0!==s&&c(this.prototype,t,s)}}static getPropertyDescriptor(t,e,i){const{get:s,set:n}=l(this.prototype,t)??{get(){return this[e]},set(t){this[e]=t}};return{get:s,set(e){const o=s?.call(this);n?.call(this,e),this.requestUpdate(t,o,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??b}static _$Ei(){if(this.hasOwnProperty(m("elementProperties")))return;const t=u(this);t.finalize(),void 0!==t.l&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(m("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(m("properties"))){const t=this.properties,e=[...d(t),...h(t)];for(const i of e)this.createProperty(i,t[i])}const t=this[Symbol.metadata];if(null!==t){const e=litPropertyMetadata.get(t);if(void 0!==e)for(const[t,i]of e)this.elementProperties.set(t,i)}this._$Eh=new Map;for(const[t,e]of this.elementProperties){const i=this._$Eu(t,e);void 0!==i&&this._$Eh.set(i,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){const e=[];if(Array.isArray(t)){const i=new Set(t.flat(1/0).reverse());for(const t of i)e.unshift(r(t))}else void 0!==t&&e.push(r(t));return e}static _$Eu(t,e){const i=e.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof t?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),void 0!==this.renderRoot&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){const t=new Map,e=this.constructor.elementProperties;for(const i of e.keys())this.hasOwnProperty(i)&&(t.set(i,this[i]),delete this[i]);t.size>0&&(this._$Ep=t)}createRenderRoot(){const i=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return((i,s)=>{if(e)i.adoptedStyleSheets=s.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(const e of s){const s=document.createElement("style"),n=t.litNonce;void 0!==n&&s.setAttribute("nonce",n),s.textContent=e.cssText,i.appendChild(s)}})(i,this.constructor.elementStyles),i}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,i){this._$AK(t,i)}_$ET(t,e){const i=this.constructor.elementProperties.get(t),s=this.constructor._$Eu(t,i);if(void 0!==s&&!0===i.reflect){const n=(void 0!==i.converter?.toAttribute?i.converter:v).toAttribute(e,i.type);this._$Em=t,null==n?this.removeAttribute(s):this.setAttribute(s,n),this._$Em=null}}_$AK(t,e){const i=this.constructor,s=i._$Eh.get(t);if(void 0!==s&&this._$Em!==s){const t=i.getPropertyOptions(s),n="function"==typeof t.converter?{fromAttribute:t.converter}:void 0!==t.converter?.fromAttribute?t.converter:v;this._$Em=s,this[s]=n.fromAttribute(e,t.type)??this._$Ej?.get(s)??null,this._$Em=null}}requestUpdate(t,e,i){if(void 0!==t){const s=this.constructor,n=this[t];if(i??=s.getPropertyOptions(t),!((i.hasChanged??y)(n,e)||i.useDefault&&i.reflect&&n===this._$Ej?.get(t)&&!this.hasAttribute(s._$Eu(t,i))))return;this.C(t,e,i)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(t,e,{useDefault:i,reflect:s,wrapped:n},o){i&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,o??e??this[t]),!0!==n||void 0!==o)||(this._$AL.has(t)||(this.hasUpdated||i||(e=void 0),this._$AL.set(t,e)),!0===s&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}const t=this.scheduleUpdate();return null!=t&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[t,e]of this._$Ep)this[t]=e;this._$Ep=void 0}const t=this.constructor.elementProperties;if(t.size>0)for(const[e,i]of t){const{wrapped:t}=i,s=this[e];!0!==t||this._$AL.has(e)||void 0===s||this.C(e,void 0,i,s)}}let t=!1;const e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(t=>t.hostUpdate?.()),this.update(e)):this._$EM()}catch(e){throw t=!1,this._$EM(),e}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(t){}firstUpdated(t){}};$.elementStyles=[],$.shadowRootOptions={mode:"open"},$[m("elementProperties")]=new Map,$[m("finalized")]=new Map,p?.({ReactiveElement:$}),(_.reactiveElementVersions??=[]).push("2.1.0");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const w=globalThis,C=w.trustedTypes,E=C?C.createPolicy("lit-html",{createHTML:t=>t}):void 0,S="$lit$",x=`lit$${Math.random().toFixed(9).slice(2)}$`,A="?"+x,T=`<${A}>`,k=document,O=()=>k.createComment(""),N=t=>null===t||"object"!=typeof t&&"function"!=typeof t,I=Array.isArray,P="[ \t\n\f\r]",M=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,U=/-->/g,R=/>/g,L=RegExp(`>|${P}(?:([^\\s"'>=/]+)(${P}*=${P}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),H=/'/g,j=/"/g,z=/^(?:script|style|textarea|title)$/i,F=(t=>(e,...i)=>({_$litType$:t,strings:e,values:i}))(1),D=Symbol.for("lit-noChange"),B=Symbol.for("lit-nothing"),q=new WeakMap,V=k.createTreeWalker(k,129);function W(t,e){if(!I(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==E?E.createHTML(e):e}const J=(t,e)=>{const i=t.length-1,s=[];let n,o=2===e?"<svg>":3===e?"<math>":"",r=M;for(let e=0;e<i;e++){const i=t[e];let a,c,l=-1,d=0;for(;d<i.length&&(r.lastIndex=d,c=r.exec(i),null!==c);)d=r.lastIndex,r===M?"!--"===c[1]?r=U:void 0!==c[1]?r=R:void 0!==c[2]?(z.test(c[2])&&(n=RegExp("</"+c[2],"g")),r=L):void 0!==c[3]&&(r=L):r===L?">"===c[0]?(r=n??M,l=-1):void 0===c[1]?l=-2:(l=r.lastIndex-c[2].length,a=c[1],r=void 0===c[3]?L:'"'===c[3]?j:H):r===j||r===H?r=L:r===U||r===R?r=M:(r=L,n=void 0);const h=r===L&&t[e+1].startsWith("/>")?" ":"";o+=r===M?i+T:l>=0?(s.push(a),i.slice(0,l)+S+i.slice(l)+x+h):i+x+(-2===l?e:h)}return[W(t,o+(t[i]||"<?>")+(2===e?"</svg>":3===e?"</math>":"")),s]};class G{constructor({strings:t,_$litType$:e},i){let s;this.parts=[];let n=0,o=0;const r=t.length-1,a=this.parts,[c,l]=J(t,e);if(this.el=G.createElement(c,i),V.currentNode=this.el.content,2===e||3===e){const t=this.el.content.firstChild;t.replaceWith(...t.childNodes)}for(;null!==(s=V.nextNode())&&a.length<r;){if(1===s.nodeType){if(s.hasAttributes())for(const t of s.getAttributeNames())if(t.endsWith(S)){const e=l[o++],i=s.getAttribute(t).split(x),r=/([.?@])?(.*)/.exec(e);a.push({type:1,index:n,name:r[2],strings:i,ctor:"."===r[1]?Y:"?"===r[1]?tt:"@"===r[1]?et:X}),s.removeAttribute(t)}else t.startsWith(x)&&(a.push({type:6,index:n}),s.removeAttribute(t));if(z.test(s.tagName)){const t=s.textContent.split(x),e=t.length-1;if(e>0){s.textContent=C?C.emptyScript:"";for(let i=0;i<e;i++)s.append(t[i],O()),V.nextNode(),a.push({type:2,index:++n});s.append(t[e],O())}}}else if(8===s.nodeType)if(s.data===A)a.push({type:2,index:n});else{let t=-1;for(;-1!==(t=s.data.indexOf(x,t+1));)a.push({type:7,index:n}),t+=x.length-1}n++}}static createElement(t,e){const i=k.createElement("template");return i.innerHTML=t,i}}function K(t,e,i=t,s){if(e===D)return e;let n=void 0!==s?i._$Co?.[s]:i._$Cl;const o=N(e)?void 0:e._$litDirective$;return n?.constructor!==o&&(n?._$AO?.(!1),void 0===o?n=void 0:(n=new o(t),n._$AT(t,i,s)),void 0!==s?(i._$Co??=[])[s]=n:i._$Cl=n),void 0!==n&&(e=K(t,n._$AS(t,e.values),n,s)),e}class Z{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){const{el:{content:e},parts:i}=this._$AD,s=(t?.creationScope??k).importNode(e,!0);V.currentNode=s;let n=V.nextNode(),o=0,r=0,a=i[0];for(;void 0!==a;){if(o===a.index){let e;2===a.type?e=new Q(n,n.nextSibling,this,t):1===a.type?e=new a.ctor(n,a.name,a.strings,this,t):6===a.type&&(e=new it(n,this,t)),this._$AV.push(e),a=i[++r]}o!==a?.index&&(n=V.nextNode(),o++)}return V.currentNode=k,s}p(t){let e=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(t,i,e),e+=i.strings.length-2):i._$AI(t[e])),e++}}class Q{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,i,s){this.type=2,this._$AH=B,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=i,this.options=s,this._$Cv=s?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode;const e=this._$AM;return void 0!==e&&11===t?.nodeType&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=K(this,t,e),N(t)?t===B||null==t||""===t?(this._$AH!==B&&this._$AR(),this._$AH=B):t!==this._$AH&&t!==D&&this._(t):void 0!==t._$litType$?this.$(t):void 0!==t.nodeType?this.T(t):(t=>I(t)||"function"==typeof t?.[Symbol.iterator])(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==B&&N(this._$AH)?this._$AA.nextSibling.data=t:this.T(k.createTextNode(t)),this._$AH=t}$(t){const{values:e,_$litType$:i}=t,s="number"==typeof i?this._$AC(t):(void 0===i.el&&(i.el=G.createElement(W(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===s)this._$AH.p(e);else{const t=new Z(s,this),i=t.u(this.options);t.p(e),this.T(i),this._$AH=t}}_$AC(t){let e=q.get(t.strings);return void 0===e&&q.set(t.strings,e=new G(t)),e}k(t){I(this._$AH)||(this._$AH=[],this._$AR());const e=this._$AH;let i,s=0;for(const n of t)s===e.length?e.push(i=new Q(this.O(O()),this.O(O()),this,this.options)):i=e[s],i._$AI(n),s++;s<e.length&&(this._$AR(i&&i._$AB.nextSibling,s),e.length=s)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t&&t!==this._$AB;){const e=t.nextSibling;t.remove(),t=e}}setConnected(t){void 0===this._$AM&&(this._$Cv=t,this._$AP?.(t))}}class X{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,i,s,n){this.type=1,this._$AH=B,this._$AN=void 0,this.element=t,this.name=e,this._$AM=s,this.options=n,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=B}_$AI(t,e=this,i,s){const n=this.strings;let o=!1;if(void 0===n)t=K(this,t,e,0),o=!N(t)||t!==this._$AH&&t!==D,o&&(this._$AH=t);else{const s=t;let r,a;for(t=n[0],r=0;r<n.length-1;r++)a=K(this,s[i+r],e,r),a===D&&(a=this._$AH[r]),o||=!N(a)||a!==this._$AH[r],a===B?t=B:t!==B&&(t+=(a??"")+n[r+1]),this._$AH[r]=a}o&&!s&&this.j(t)}j(t){t===B?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}}class Y extends X{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===B?void 0:t}}class tt extends X{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==B)}}class et extends X{constructor(t,e,i,s,n){super(t,e,i,s,n),this.type=5}_$AI(t,e=this){if((t=K(this,t,e,0)??B)===D)return;const i=this._$AH,s=t===B&&i!==B||t.capture!==i.capture||t.once!==i.once||t.passive!==i.passive,n=t!==B&&(i===B||s);s&&this.element.removeEventListener(this.name,this,i),n&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}}class it{constructor(t,e,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){K(this,t)}}const st=w.litHtmlPolyfillSupport;st?.(G,Q),(w.litHtmlVersions??=[]).push("3.3.0");const nt=globalThis;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */class ot extends ${constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){const e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=((t,e,i)=>{const s=i?.renderBefore??e;let n=s._$litPart$;if(void 0===n){const t=i?.renderBefore??null;s._$litPart$=n=new Q(e.insertBefore(O(),t),t,void 0,i??{})}return n._$AI(t),n})(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return D}}ot._$litElement$=!0,ot.finalized=!0,nt.litElementHydrateSupport?.({LitElement:ot});const rt=nt.litElementPolyfillSupport;rt?.({LitElement:ot}),(nt.litElementVersions??=[]).push("4.2.0");const at="simple_timer",ct=[15,30,60,90,120,150];console.info("%c TIMER-CARD %c v1.0.9 ","color: orange; font-weight: bold; background: black","color: white; font-weight: bold; background: dimgray");customElements.define("timer-card",class extends ot{constructor(){super(...arguments),this._countdownInterval=null,this._liveRuntimeSeconds=0,this._timeRemaining=null,this.buttons=[],this._validationMessage=null,this._notificationSentForCurrentCycle=!1,this._entitiesLoaded=!1,this._effectiveSwitchEntity=null,this._effectiveSensorEntity=null}static get properties(){return{hass:{type:Object},_config:{type:Object},_timeRemaining:{state:!0},_entitiesLoaded:{state:!0},_effectiveSwitchEntity:{state:!0},_effectiveSensorEntity:{state:!0}}}static async getConfigElement(){return await Promise.resolve().then(function(){return ut}),document.createElement("timer-card-editor")}static getStubConfig(t){console.log("TimerCard: Generating stub config with hass object:",t);let e=null;for(const i of Object.keys(t.states)){const s=t.states[i];if(i.startsWith("sensor.")&&"string"==typeof s.attributes.entry_id&&"string"==typeof s.attributes.switch_entity_id){e=s.attributes.entry_id,console.info(`TimerCard: getStubConfig auto-selected first instance: '${e}' from sensor '${i}'`);break}}return{type:"custom:timer-card",timer_instance_id:e,timer_buttons:[...ct],card_title:"Simple Timer",show_seconds:!1}}setConfig(t){this._config={type:t.type||"custom:timer-card",timer_buttons:this._getValidatedTimerButtons(t.timer_buttons),card_title:t.card_title||null,show_seconds:t.show_seconds||!1},t.timer_instance_id&&(this._config.timer_instance_id=t.timer_instance_id),t.entity&&(this._config.entity=t.entity),t.sensor_entity&&(this._config.sensor_entity=t.sensor_entity),t.notification_entity&&(this._config.notification_entity=t.notification_entity),this.buttons=[...this._config.timer_buttons],this._liveRuntimeSeconds=0,this._notificationSentForCurrentCycle=!1,this._effectiveSwitchEntity=null,this._effectiveSensorEntity=null,this._entitiesLoaded=!1,console.log(`TimerCard: setConfig completed. Configured instance ID: ${this._config.timer_instance_id}, Buttons: ${this.buttons.length}, Show seconds: ${this._config.show_seconds}`)}_getValidatedTimerButtons(t){let e=[];if(this._validationMessage=null,Array.isArray(t)){const i=[];return t.forEach(t=>{const s=Number(t);Number.isInteger(s)&&s>0&&s<=1e3?e.push(s):i.push(t)}),i.length>0&&(this._validationMessage=`Invalid timer values ignored: ${i.join(", ")}. Only positive integers up to 1000 are allowed.`),e.sort((t,e)=>t-e),e}return null==t||(console.warn(`TimerCard: Invalid timer_buttons type (${typeof t}):`,t,"- using empty array"),this._validationMessage=`Invalid timer_buttons configuration. Expected array, got ${typeof t}.`),[]}_determineEffectiveEntities(){var t,e;let i=null,s=null,n=!1;if(this.hass&&this.hass.states){if(null===(t=this._config)||void 0===t?void 0:t.timer_instance_id){const t=this._config.timer_instance_id,e=Object.keys(this.hass.states).filter(t=>t.startsWith("sensor.")).find(e=>{const i=this.hass.states[e];return i.attributes.entry_id===t&&"string"==typeof i.attributes.switch_entity_id});if(e){s=e,i=this.hass.states[e].attributes.switch_entity_id,i&&this.hass.states[i]?n=!0:console.warn(`TimerCard: Configured instance '${t}' sensor '${s}' links to missing or invalid switch '${i}'.`)}else console.warn(`TimerCard: Configured timer_instance_id '${t}' does not have a corresponding simple_timer sensor found.`)}if(!n&&(null===(e=this._config)||void 0===e?void 0:e.sensor_entity)){const t=this.hass.states[this._config.sensor_entity];t&&"string"==typeof t.attributes.entry_id&&"string"==typeof t.attributes.switch_entity_id?(s=this._config.sensor_entity,i=t.attributes.switch_entity_id,i&&this.hass.states[i]?(n=!0,console.info(`TimerCard: Using manually configured sensor_entity: Sensor '${s}', Switch '${i}'.`)):console.warn(`TimerCard: Manually configured sensor '${s}' links to missing or invalid switch '${i}'.`)):console.warn(`TimerCard: Manually configured sensor_entity '${this._config.sensor_entity}' not found or missing required attributes.`)}if(!n){const t=Object.keys(this.hass.states).filter(t=>t.startsWith("sensor.")).find(t=>{const e=this.hass.states[t];return"string"==typeof e.attributes.entry_id&&"string"==typeof e.attributes.switch_entity_id});if(t){s=t,i=this.hass.states[t].attributes.switch_entity_id,i&&this.hass.states[i]?(n=!0,console.info(`TimerCard: Auto-detected first instance: Sensor '${s}', Switch '${i}'.`)):console.warn(`TimerCard: Auto-detected sensor '${s}' links to missing or invalid switch '${i}'.`)}else console.info("TimerCard: No simple_timer sensor found for auto-detection.")}this._effectiveSwitchEntity===i&&this._effectiveSensorEntity===s||(this._effectiveSwitchEntity=i,this._effectiveSensorEntity=s,this.requestUpdate()),this._entitiesLoaded=n}else this._entitiesLoaded=!1}_getEntryId(){if(!this._effectiveSensorEntity||!this.hass||!this.hass.states)return console.error("Timer-card: _getEntryId called without a valid effective sensor entity."),null;const t=this.hass.states[this._effectiveSensorEntity];return t&&t.attributes.entry_id?t.attributes.entry_id:(console.error("Could not determine entry_id from effective sensor_entity attributes:",this._effectiveSensorEntity),null)}_sendNotification(t){var e;if(!this.hass||!this.hass.callService||!(null===(e=this._config)||void 0===e?void 0:e.notification_entity)||"none_selected"===this._config.notification_entity)return;const i=this._config.notification_entity.split("."),s=i[0],n=i.slice(1).join(".");this.hass.callService(s,n,{message:t}).catch(t=>{console.warn("Timer-card: Notification failed:",t)})}_startTimer(t){if(!this._entitiesLoaded||!this.hass||!this.hass.callService)return void console.error("Timer-card: Cannot start timer. Entities not loaded or callService unavailable.");const e=this._getEntryId();if(!e)return void console.error("Timer-card: Entry ID not found for starting timer.");const i=this._effectiveSwitchEntity;this.hass.callService("homeassistant","turn_on",{entity_id:i}).then(()=>{var i;this.hass.callService(at,"start_timer",{entry_id:e,duration:t}),this._sendNotification(`${(null===(i=this._config)||void 0===i?void 0:i.card_title)||"Timer"} was turned on for ${t} minutes`)}).catch(t=>{console.error("Timer-card: Error turning on switch or starting timer:",t)}),this._notificationSentForCurrentCycle=!1}_cancelTimer(){if(!this._entitiesLoaded||!this.hass||!this.hass.callService)return void console.error("Timer-card: Cannot cancel timer. Entities not loaded or callService unavailable.");const t=this._getEntryId();t?(this.hass.callService(at,"cancel_timer",{entry_id:t}).then(()=>{this._sendTimerFinishedNotification()}).catch(t=>{console.error("Timer-card: Error cancelling timer:",t)}),this._notificationSentForCurrentCycle=!1):console.error("Timer-card: Entry ID not found for cancelling timer.")}_togglePower(){var t;if(!(this._entitiesLoaded&&this.hass&&this.hass.states&&this.hass.callService))return void console.error("Timer-card: Cannot toggle power. Entities not loaded or services unavailable.");const e=this._effectiveSwitchEntity,i=this._effectiveSensorEntity,s=this.hass.states[e];if(!s)return void console.warn(`Timer-card: Switch entity '${e}' not found during toggle.`);const n=this.hass.states[i],o=n&&"active"===n.attributes.timer_state;if("on"===s.state)if(o)this._cancelTimer(),console.log(`Timer-card: Cancelling active timer for switch: ${e}`);else{this.hass.callService("homeassistant","turn_off",{entity_id:e});const i=this.hass.states[this._effectiveSensorEntity];if(i){const e=parseFloat(i.state)||0,{formattedTime:s,label:n}=this._formatTimeForNotification(e);this._sendNotification(`${(null===(t=this._config)||void 0===t?void 0:t.card_title)||"Timer"} was turned off - daily usage ${s} ${n}`)}console.log(`Timer-card: Manually turning off switch: ${e}`)}else this.hass.callService("homeassistant","turn_on",{entity_id:e}).then(()=>{var t;this._sendNotification(`${(null===(t=this._config)||void 0===t?void 0:t.card_title)||"Timer"} started`),console.log(`Timer-card: Manually turning on switch: ${e}`)}).catch(t=>{console.error("Timer-card: Error manually turning on switch:",t)}),this._notificationSentForCurrentCycle=!1}_showMoreInfo(){if(!this._entitiesLoaded||!this.hass)return void console.error("Timer-card: Cannot show more info. Entities not loaded.");const t=this._effectiveSensorEntity,e=new CustomEvent("hass-more-info",{bubbles:!0,composed:!0,detail:{entityId:t}});this.dispatchEvent(e)}connectedCallback(){super.connectedCallback(),this._determineEffectiveEntities(),this._updateLiveRuntime(),this._updateCountdown()}disconnectedCallback(){super.disconnectedCallback(),this._stopCountdown(),this._stopLiveRuntime()}updated(t){(t.has("hass")||t.has("_config"))&&(this._determineEffectiveEntities(),this._updateLiveRuntime(),this._updateCountdown())}_updateLiveRuntime(){this._liveRuntimeSeconds=0}_stopLiveRuntime(){this._liveRuntimeSeconds=0}_formatTimeForNotification(t){var e;if(null===(e=this._config)||void 0===e?void 0:e.show_seconds){const e=Math.floor(t),i=Math.floor(e/3600),s=Math.floor(e%3600/60),n=e%60;return{formattedTime:`${i.toString().padStart(2,"0")}:${s.toString().padStart(2,"0")}:${n.toString().padStart(2,"0")}`,label:"(hh:mm:ss)"}}{const e=Math.floor(t/60),i=e%60;return{formattedTime:`${Math.floor(e/60).toString().padStart(2,"0")}:${i.toString().padStart(2,"0")}`,label:"(hh:mm)"}}}_updateCountdown(){if(!this._entitiesLoaded||!this.hass||!this.hass.states)return void this._stopCountdown();const t=this.hass.states[this._effectiveSensorEntity];if(!t||"active"!==t.attributes.timer_state)return this._stopCountdown(),void(this._notificationSentForCurrentCycle=!1);if(!this._countdownInterval){const e=t.attributes.timer_finishes_at;if(void 0===e)return console.warn("Timer-card: timer_finishes_at is undefined for active timer. Stopping countdown."),void this._stopCountdown();const i=new Date(e).getTime(),s=()=>{const t=(new Date).getTime(),e=Math.max(0,Math.round((i-t)/1e3));this._timeRemaining=`${Math.floor(e/60).toString().padStart(2,"0")}:${(e%60).toString().padStart(2,"0")}`,0===e&&(this._stopCountdown(),this._notificationSentForCurrentCycle||(this._notificationSentForCurrentCycle=!0,setTimeout(()=>{var t;if(!this.hass||!this._effectiveSensorEntity)return;const e=this.hass.states[this._effectiveSensorEntity];if(!e)return;const i=parseFloat(e.state)||0,{formattedTime:s,label:n}=this._formatTimeForNotification(i);this._sendNotification(`${(null===(t=this._config)||void 0===t?void 0:t.card_title)||"Timer"} was turned off - daily usage ${s} ${n}`)},500)))};this._countdownInterval=window.setInterval(s,500),s()}}_stopCountdown(){this._countdownInterval&&(window.clearInterval(this._countdownInterval),this._countdownInterval=null),this._timeRemaining=null}_sendTimerFinishedNotification(){var t;if(!this._entitiesLoaded||!this.hass||!this.hass.states)return;const e=this.hass.states[this._effectiveSensorEntity];if(!e)return;const i=parseFloat(e.state)||0,{formattedTime:s,label:n}=this._formatTimeForNotification(i);this._sendNotification(`${(null===(t=this._config)||void 0===t?void 0:t.card_title)||"Timer"} finished – daily usage ${s} ${n}`)}render(){var t,e,i,s,n;let o=null,r=!1;if(this.hass){if(!this._entitiesLoaded)if(null===(t=this._config)||void 0===t?void 0:t.timer_instance_id){const t=Object.values(this.hass.states).find(t=>t.attributes.entry_id===this._config.timer_instance_id&&t.entity_id.startsWith("sensor."));t?"string"==typeof t.attributes.switch_entity_id&&t.attributes.switch_entity_id&&this.hass.states[t.attributes.switch_entity_id]?(o="Loading Timer Control Card. Please wait...",r=!1):(o=`Timer Control Instance '${this._config.timer_instance_id}' linked to missing or invalid switch '${t.attributes.switch_entity_id}'. Please check instance configuration.`,r=!0):(o=`Timer Control Instance '${this._config.timer_instance_id}' not found. Please select a valid instance in the card editor.`,r=!0)}else if(null===(e=this._config)||void 0===e?void 0:e.sensor_entity){const t=this.hass.states[this._config.sensor_entity];t?"string"==typeof t.attributes.switch_entity_id&&t.attributes.switch_entity_id&&this.hass.states[t.attributes.switch_entity_id]?(o="Loading Timer Control Card. Please wait...",r=!1):(o=`Configured Timer Control Sensor '${this._config.sensor_entity}' is invalid or its linked switch '${t.attributes.switch_entity_id}' is missing. Please select a valid instance.`,r=!0):(o=`Configured Timer Control Sensor '${this._config.sensor_entity}' not found. Please select a valid instance in the card editor.`,r=!0)}else o="Select a Timer Control Instance from the dropdown in the card editor to link this card.",r=!1}else o="Home Assistant object (hass) not available. Card cannot load.",r=!0;if(o)return F`<ha-card><div class="${r?"warning":"placeholder"}">${o}</div></ha-card>`;const a=this.hass.states[this._effectiveSwitchEntity],c=this.hass.states[this._effectiveSensorEntity],l="on"===a.state,d="active"===c.attributes.timer_state,h=c.attributes.timer_duration||0,u=l&&!d;let _,f,g=parseFloat(c.state)||0;if(null===(i=this._config)||void 0===i?void 0:i.show_seconds){const t=Math.floor(g),e=Math.floor(t/3600),i=Math.floor(t%3600/60),s=t%60;_=`${e.toString().padStart(2,"0")}:${i.toString().padStart(2,"0")}:${s.toString().padStart(2,"0")}`,f="Daily Usage (hh:mm:ss)"}else{const t=Math.floor(g/60),e=t%60;_=`${Math.floor(t/60).toString().padStart(2,"0")}:${e.toString().padStart(2,"0")}`,f="Daily Usage (hh:mm)"}const p=c.attributes.watchdog_message;return F`
      <ha-card>
        ${(null===(s=this._config)||void 0===s?void 0:s.card_title)?F`<div class="card-title">${this._config.card_title}</div>`:""}
        ${p?F`
          <div class="status-message warning watchdog-banner">
            <ha-icon icon="mdi:alert-outline" class="status-icon"></ha-icon>
            <span class="status-text">${p}</span>
          </div>
        `:""}
        <div class="main-grid">
          <div class="button power-button ${l?"on":""}" @click=${this._togglePower}><ha-icon icon="mdi:power"></ha-icon></div>
          <div class="button readonly" @click=${this._showMoreInfo}>
            <span class="daily-time-text ${(null===(n=this._config)||void 0===n?void 0:n.show_seconds)?"with-seconds":""}">${_}</span>
            <span class="runtime-label">${f}</span>
          </div>
        </div>
        <div class="button-grid">
          ${this.buttons.map(t=>{const e=d&&h===t,i=u||d&&!e;return F`
              <div class="button timer-button ${e?"active":""} ${i?"disabled":""}" @click=${()=>{e?this._cancelTimer():i||this._startTimer(t)}}>
                ${e&&this._timeRemaining?F`<span class="countdown-text">${this._timeRemaining}</span>`:F`<div class="timer-button-content"><span class="timer-button-value">${t}</span><span class="timer-button-unit">Min</span></div>`}
              </div>
            `})}
        </div>
        ${this._validationMessage?F`
          <div class="status-message warning">
            <ha-icon icon="mdi:alert-outline" class="status-icon"></ha-icon>
            <span class="status-text">${this._validationMessage}</span>
          </div>
        `:""}
      </ha-card>
    `}static get styles(){return o`
      :host { display: block; }
      .ha-card {
        padding: 0;
      }
      .card-title {
        font-size: 1.2em;
        font-weight: bold;
        text-align: center;
        padding: 12px;
        background-color: var(--primary-color-faded, rgba(150, 210, 230, 0.2));
        border-bottom: 1px solid var(--divider-color);
        color: var(--primary-text-color);
        border-radius: 12px 12px 0 0;
        margin-bottom: 12px;
        white-space: pre-wrap;
        word-break: break-word;
      }
      .card-title pre {
        margin: 0;
        padding: 0;
        font-family: inherit;
        font-size: inherit;
        color: inherit;
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
    `}}),window.customCards=window.customCards||[],window.customCards.push({type:"timer-card",name:"Simple Timer Card",description:"A card for the Simple Timer integration."});const lt="instance_title",dt=[15,30,60,90,120,150];class ht extends ot{constructor(){super(),this._configFullyLoaded=!1,this._timerInstancesOptions=[],this._allTimerOptions=[1,15,30,45,60,75,90,105,120,135,150,165,180],this._config={type:"custom:timer-card",timer_buttons:[...dt],notification_entity:null,timer_instance_id:null,card_title:null,show_seconds:!1}}async _getSimpleTimerInstances(){if(!this.hass||!this.hass.states)return console.warn("TimerCardEditor: hass.states not available when trying to fetch instances from states."),[];const t=new Map;for(const e in this.hass.states){const i=this.hass.states[e];if(e.startsWith("sensor.")&&e.includes("runtime")&&i.attributes.entry_id&&"string"==typeof i.attributes.entry_id&&i.attributes.switch_entity_id&&"string"==typeof i.attributes.switch_entity_id){const s=i.attributes.entry_id,n=i.attributes[lt];let o=`Timer Control (${s.substring(0,8)})`;console.debug(`TimerCardEditor: Processing sensor ${e} (Entry: ${s})`),console.debug(`TimerCardEditor: Found raw attribute '${lt}': ${n}`),console.debug("TimerCardEditor: Type of raw attribute: "+typeof n),n&&"string"==typeof n&&""!==n.trim()?(o=n.trim(),console.debug(`TimerCardEditor: Using '${lt}' for label: "${o}"`)):console.warn(`TimerCardEditor: Sensor '${e}' has no valid '${lt}' attribute. Falling back to entry ID based label: "${o}".`),t.has(s)?console.debug(`TimerCardEditor: Skipping duplicate entry_id: ${s}`):(t.set(s,{value:s,label:o}),console.debug(`TimerCardEditor: Added instance: ${o} (${s}) from sensor: ${e}`))}}const e=Array.from(t.values());return e.sort((t,e)=>t.label.localeCompare(e.label)),0===e.length?console.info("TimerCardEditor: No Simple Timer integration instances found by scanning hass.states."):console.info("TimerCardEditor: Found Simple Timer instances by scanning states:",e),e}_getNotificationServiceTargets(){var t,e;if(!this.hass||!this.hass.services)return[];const i=[];if(this.hass.services.notify)for(const e in this.hass.services.notify)if("send"!==e&&!e.includes("_all")&&!e.includes("_group")){const s=(null===(t=this.hass.services.notify[e])||void 0===t?void 0:t.description)||e;i.push({value:`notify.${e}`,label:s})}for(const t in this.hass.services)if(t.includes("telegram")||t.includes("mobile_app")){const s=this.hass.services[t];for(const n in s)if(n.includes("send")||n.includes("message")||n.includes("notify")){const o=`${t}.${n}`;if(!i.some(t=>t.value===o)){const t=(null===(e=s[n])||void 0===e?void 0:e.description)||o;i.push({value:o,label:t})}}}return i.sort((t,e)=>t.label.localeCompare(e.label)),i}_getValidatedTimerButtons(t){if(Array.isArray(t)){const e=[];return t.forEach(t=>{const i=Number(t);Number.isInteger(i)&&i>0&&i<=1e3&&e.push(i)}),e.sort((t,e)=>t-e),console.log(`TimerCardEditor: Using ${e.length} timer buttons from config:`,e),e}return null==t?(console.log("TimerCardEditor: No timer_buttons in config, using empty array."),[]):(console.warn(`TimerCardEditor: Invalid timer_buttons type (${typeof t}):`,t,"- using empty array"),[])}async setConfig(t){console.log("TimerCardEditor: setConfig called with:",t);const e=Object.assign({},this._config),i=this._getValidatedTimerButtons(t.timer_buttons),s={type:t.type||"custom:timer-card",timer_buttons:i,card_title:t.card_title||null,show_seconds:t.show_seconds||!1};t.timer_instance_id?(s.timer_instance_id=t.timer_instance_id,console.info(`TimerCardEditor: setConfig PRESERVING existing timer_instance_id: '${t.timer_instance_id}'`)):console.info("TimerCardEditor: setConfig - no timer_instance_id in config, will be auto-selected later"),t.entity&&(s.entity=t.entity),t.sensor_entity&&(s.sensor_entity=t.sensor_entity),t.notification_entity&&(s.notification_entity=t.notification_entity),this._config=s,this._configFullyLoaded=!0,console.log("TimerCardEditor: setConfig result:",this._config),JSON.stringify(e)!==JSON.stringify(this._config)?(console.log("TimerCardEditor: Config changed, dispatching config-changed event"),this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:this._config}}))):console.log("TimerCardEditor: Config unchanged, not dispatching event"),this.requestUpdate()}get _schema(){const t=this._timerInstancesOptions||[],e=this._getNotificationServiceTargets(),i=t.length>0?t:[{value:"none_found",label:"No Simple Timer Instances Found"}],s=[{value:"none_selected",label:"None"}];return e.forEach(t=>s.push(t)),[{name:"card_title",label:"Card Title (Optional)",selector:{text:{type:"text"}}},{name:"timer_instance_id",label:"Simple Timer Instance",required:!0,selector:{select:{options:i,mode:"dropdown"}}},{name:"show_seconds",label:"Show Seconds in Daily Usage",selector:{boolean:{}}},{name:"notification_entity",label:"Notification Service Target (Optional)",selector:{select:{options:s,custom_value:!1}}}]}connectedCallback(){super.connectedCallback(),this.hass?this._fetchTimerInstances():console.warn("TimerCardEditor: hass not available on connectedCallback. Deferring instance fetch.")}updated(t){var e;super.updated(t),t.has("hass")&&this.hass&&((null===(e=t.get("hass"))||void 0===e?void 0:e.states)===this.hass.states&&0!==this._timerInstancesOptions.length||(console.log("TimerCardEditor: hass.states changed or instances not yet fetched, re-fetching instances."),this._fetchTimerInstances()))}async _fetchTimerInstances(){var t,e,i;if(this.hass){if(console.log(`TimerCardEditor: _fetchTimerInstances called. Config loaded: ${this._configFullyLoaded}, Current config timer_instance_id: '${null===(t=this._config)||void 0===t?void 0:t.timer_instance_id}'`),this._timerInstancesOptions=await this._getSimpleTimerInstances(),console.log(`TimerCardEditor: Found ${this._timerInstancesOptions.length} instances:`,this._timerInstancesOptions),!this._configFullyLoaded)return console.info("TimerCardEditor: Config not fully loaded yet, skipping any auto-selection logic"),void this.requestUpdate();const s=!(null===(e=this._config)||void 0===e?void 0:e.timer_instance_id)||"none_found"===this._config.timer_instance_id||""===this._config.timer_instance_id,n=this._timerInstancesOptions.length>0;if(console.log(`TimerCardEditor: hasNoInstanceConfigured: ${s}, hasAvailableInstances: ${n}`),s&&n){const t=this._timerInstancesOptions[0];console.info(`TimerCardEditor: AUTO-SELECTING first available instance (no valid instance configured): '${t.value}' (${t.label})`);const e=Object.assign(Object.assign({},this._config),{timer_instance_id:t.value});this._config=e,this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:this._config},bubbles:!0,composed:!0}))}else if((null===(i=this._config)||void 0===i?void 0:i.timer_instance_id)&&n){if(this._timerInstancesOptions.some(t=>t.value===this._config.timer_instance_id))console.info(`TimerCardEditor: PRESERVING existing valid instance: '${this._config.timer_instance_id}'`);else{console.warn(`TimerCardEditor: Previously configured instance '${this._config.timer_instance_id}' no longer exists. Auto-selecting first available instance.`);const t=this._timerInstancesOptions[0],e=Object.assign(Object.assign({},this._config),{timer_instance_id:t.value});this._config=e,this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:this._config},bubbles:!0,composed:!0}))}}else n||console.warn("TimerCardEditor: No simple timer instances found.");this.requestUpdate()}}_handleTimerCheckboxChange(t){var e,i,s,n,o,r;const a=t.target,c=parseInt(a.value),l=a.checked;let d=Array.isArray(null===(e=this._config)||void 0===e?void 0:e.timer_buttons)?[...this._config.timer_buttons]:[];l?d.includes(c)||d.push(c):d=d.filter(t=>t!==c),d.sort((t,e)=>t-e);const h={type:this._config.type,timer_buttons:d,show_seconds:this._config.show_seconds||!1};(null===(i=this._config)||void 0===i?void 0:i.timer_instance_id)&&(h.timer_instance_id=this._config.timer_instance_id),(null===(s=this._config)||void 0===s?void 0:s.entity)&&(h.entity=this._config.entity),(null===(n=this._config)||void 0===n?void 0:n.sensor_entity)&&(h.sensor_entity=this._config.sensor_entity),(null===(o=this._config)||void 0===o?void 0:o.notification_entity)&&(h.notification_entity=this._config.notification_entity),(null===(r=this._config)||void 0===r?void 0:r.card_title)&&(h.card_title=this._config.card_title),this._config=h,this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:this._config},bubbles:!0,composed:!0})),this.requestUpdate()}render(){var t,e;return this.hass?F`
      <ha-form
        .hass=${this.hass}
        .data=${this._config}
        .schema=${this._schema}
        @value-changed=${this._valueChanged}
      ></ha-form>

      <div class="card-config-group">
        <h3>Select your timers (Minutes)</h3>
        <div class="checkbox-grid">
          ${this._allTimerOptions.map(t=>{var e;return F`
            <label class="checkbox-label">
              <input
                type="checkbox"
                value="${t}"
                .checked=${Array.isArray(null===(e=this._config)||void 0===e?void 0:e.timer_buttons)&&this._config.timer_buttons.includes(t)}
                @change=${this._handleTimerCheckboxChange}
              >
              ${t}
            </label>
          `})}
        </div>
        <div class="timer-buttons-info">
          ${(null===(e=null===(t=this._config)||void 0===t?void 0:t.timer_buttons)||void 0===e?void 0:e.length)?"":F`
            <p class="info-text">ℹ️ No timer buttons selected. Only power toggle and daily usage will be shown.</p>
          `}
        </div>
      </div>
    `:F``}_valueChanged(t){t.stopPropagation();const e=t.detail.value;if(!this._config)return void console.warn("TimerCardEditor: _config is null in _valueChanged, deferring update.");const i={type:e.type||this._config.type||"custom:timer-card",timer_buttons:this._config.timer_buttons,show_seconds:void 0!==e.show_seconds?e.show_seconds:this._config.show_seconds||!1};e.timer_instance_id&&"none_found"!==e.timer_instance_id?i.timer_instance_id=e.timer_instance_id:delete i.timer_instance_id,this._config.entity&&(i.entity=this._config.entity),this._config.sensor_entity&&(i.sensor_entity=this._config.sensor_entity),e.notification_entity&&"none_selected"!==e.notification_entity?i.notification_entity=e.notification_entity:"none_selected"===e.notification_entity?delete i.notification_entity:this._config.notification_entity&&(i.notification_entity=this._config.notification_entity),e.card_title&&""!==e.card_title?i.card_title=e.card_title:delete i.card_title,JSON.stringify(this._config)!==JSON.stringify(i)&&(this._config=i,this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:this._config},bubbles:!0,composed:!0})),this.requestUpdate())}static get styles(){return o`
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
    `}}ht.properties={hass:{type:Object},_config:{type:Object}},customElements.define("timer-card-editor",ht);var ut=Object.freeze({__proto__:null});
//# sourceMappingURL=timer-card.js.map
