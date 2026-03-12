System.register(["jimu-core","jimu-ui/advanced/setting-components","jimu-ui","jimu-ui/advanced/map"],(function(e,t){var a={},s={},i={},n={};return{setters:[function(e){a.React=e.React,a.classNames=e.classNames,a.css=e.css,a.jsx=e.jsx,a.polished=e.polished,a.useIntl=e.useIntl},function(e){s.MapWidgetSelector=e.MapWidgetSelector,s.SettingCollapse=e.SettingCollapse,s.SettingRow=e.SettingRow,s.SettingSection=e.SettingSection},function(e){i.Button=e.Button,i.Checkbox=e.Checkbox,i.Icon=e.Icon,i.Label=e.Label,i.NumericInput=e.NumericInput,i.Radio=e.Radio,i.Switch=e.Switch,i.defaultMessages=e.defaultMessages},function(e){n.DrawingElevationMode3D=e.DrawingElevationMode3D,n.useMeasurementsUnitsInfos=e.useMeasurementsUnitsInfos}],execute:function(){e((()=>{var e={31027:e=>{e.exports='<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16"><path fill="#000" fill-rule="evenodd" d="M12 6.5c0 .527-.074 1.036-.212 1.518l.912.438a6.5 6.5 0 1 0-6.586 4.533l-.077-1.008A5.5 5.5 0 1 1 12 6.5m-9 0a3.5 3.5 0 0 0 2.88 3.445L5.8 8.901a2.501 2.501 0 1 1 3.194-2.224l.949.456A3.5 3.5 0 1 0 3 6.5M15.5 11l-5 1-3 4-1-9.5zm-5.57.094-1.702 2.269-.542-5.152 4.76 2.38z" clip-rule="evenodd"></path></svg>'},60846:e=>{e.exports='<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16"><path fill="#000" fill-rule="evenodd" d="M0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8m1 0a7 7 0 0 0 7 7 7.01 7.01 0 0 0 7-7A7 7 0 1 0 1 8" clip-rule="evenodd"></path></svg>'},74919:e=>{e.exports='<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16"><path fill="#000" fill-rule="evenodd" d="M7 2h2a2 2 0 0 1 2 2v7.817l-3 2.812-3-2.812V4a2 2 0 0 1 2-2m5 2v8.25L8 16l-4-3.75V4a3 3 0 0 1 3-3h2a3 3 0 0 1 3 3M9 6a1 1 0 1 1-2 0 1 1 0 0 1 2 0m1 0a2 2 0 1 1-4 0 2 2 0 0 1 4 0" clip-rule="evenodd"></path></svg>'},42588:e=>{e.exports='<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16"><path fill="#000" fill-rule="evenodd" d="M1 3.429V16h14V0L6.833 6.857zM14 2v13H2V5.114l4.182 2.51a1.2 1.2 0 0 0 1.398-.118z" clip-rule="evenodd"></path></svg>'},86058:e=>{e.exports='<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16"><path fill="#000" d="M14.582 5 11 10.949V12H9v-1.274L5.316 7h-.515L2 12.383V14H0v-2h1.073L4 6.374V5h2v1.27L9.688 10h.716L14 4.029V3h2v2z"></path></svg>'},2985:e=>{e.exports='<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16"><path fill="#000" fill-rule="evenodd" d="M2.002 1H14A1 1 0 0 1 15 2.002v11.997A1 1 0 0 1 14 15H2a1 1 0 0 1-1-1V2a1 1 0 0 1 1.002-1M2 14h12V2H2z" clip-rule="evenodd"></path></svg>'},91108:e=>{e.exports="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTA4IiBoZWlnaHQ9IjcyIiB2aWV3Qm94PSIwIDAgMTA4IDcyIiBmaWxsPSJub25lIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPg0KPHJlY3QgeD0iOCIgeT0iOCIgd2lkdGg9IjkyIiBoZWlnaHQ9IjU2IiBmaWxsPSIjMjgyODI4Ii8+DQo8cmVjdCB4PSIxMyIgeT0iNDAiIHdpZHRoPSI1MyIgaGVpZ2h0PSI2IiBmaWxsPSIjNkE2QTZBIi8+DQo8cmVjdCB4PSIxMyIgeT0iMzIiIHdpZHRoPSI4MSIgaGVpZ2h0PSIxIiBmaWxsPSIjNDQ0NDQ0Ii8+DQo8cmVjdCB4PSIxMyIgeT0iNTIiIHdpZHRoPSI4MSIgaGVpZ2h0PSI2IiBmaWxsPSIjNkE2QTZBIi8+DQo8cmVjdCB4PSIxMyIgeT0iMTQiIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgcng9IjIiIGZpbGw9IiM2QTZBNkEiLz4NCjxyZWN0IHg9IjI5IiB5PSIxNCIgd2lkdGg9IjEyIiBoZWlnaHQ9IjEyIiByeD0iMiIgZmlsbD0iIzZBNkE2QSIvPg0KPHJlY3QgeD0iNDUiIHk9IjE0IiB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHJ4PSIyIiBmaWxsPSIjNkE2QTZBIi8+DQo8cmVjdCB4PSI2MSIgeT0iMTQiIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgcng9IjIiIGZpbGw9IiM2QTZBNkEiLz4NCjxyZWN0IHg9Ijc3IiB5PSIxNCIgd2lkdGg9IjEiIGhlaWdodD0iMTIiIGZpbGw9IiM0NDQ0NDQiLz4NCjxyZWN0IHg9IjgyIiB5PSIxNCIgd2lkdGg9IjEyIiBoZWlnaHQ9IjEyIiByeD0iMiIgZmlsbD0iIzZBNkE2QSIvPg0KPC9zdmc+DQo="},69125:e=>{e.exports="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTA4IiBoZWlnaHQ9IjcyIiB2aWV3Qm94PSIwIDAgMTA4IDcyIiBmaWxsPSJub25lIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPg0KPHJlY3QgeD0iOCIgeT0iMjYiIHdpZHRoPSI5MiIgaGVpZ2h0PSIyMCIgZmlsbD0iIzI4MjgyOCIvPg0KPHJlY3QgeD0iMTQiIHk9IjMwIiB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHJ4PSIyIiBmaWxsPSIjNkE2QTZBIi8+DQo8cmVjdCB4PSIzMCIgeT0iMzAiIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgcng9IjIiIGZpbGw9IiM2QTZBNkEiLz4NCjxyZWN0IHg9IjQ2IiB5PSIzMCIgd2lkdGg9IjEyIiBoZWlnaHQ9IjEyIiByeD0iMiIgZmlsbD0iIzZBNkE2QSIvPg0KPHJlY3QgeD0iNjIiIHk9IjMwIiB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHJ4PSIyIiBmaWxsPSIjNkE2QTZBIi8+DQo8cmVjdCB4PSI3OCIgeT0iMzAiIHdpZHRoPSIxIiBoZWlnaHQ9IjEyIiBmaWxsPSIjNDQ0NDQ0Ii8+DQo8cmVjdCB4PSI4MyIgeT0iMzAiIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgcng9IjIiIGZpbGw9IiM2QTZBNkEiLz4NCjwvc3ZnPg0K"},79244:e=>{"use strict";e.exports=a},14321:e=>{"use strict";e.exports=i},48993:e=>{"use strict";e.exports=n},79298:e=>{"use strict";e.exports=s}},t={};function o(a){var s=t[a];if(void 0!==s)return s.exports;var i=t[a]={exports:{}};return e[a](i,i.exports,o),i.exports}o.n=e=>{var t=e&&e.__esModule?()=>e.default:()=>e;return o.d(t,{a:t}),t},o.d=(e,t)=>{for(var a in t)o.o(t,a)&&!o.o(e,a)&&Object.defineProperty(e,a,{enumerable:!0,get:t[a]})},o.o=(e,t)=>Object.prototype.hasOwnProperty.call(e,t),o.r=e=>{"undefined"!=typeof Symbol&&Symbol.toStringTag&&Object.defineProperty(e,Symbol.toStringTag,{value:"Module"}),Object.defineProperty(e,"__esModule",{value:!0})},o.p="";var l={};return o.p=window.jimuConfig.baseUrl,(()=>{"use strict";o.r(l),o.d(l,{__set_webpack_public_path__:()=>_,default:()=>$});var e,t,a,s=o(79244),i=o(79298),n=o(14321);!function(e){e.Panel="Panel",e.Toolbar="Toolbar"}(e||(e={})),function(e){e.Continuous="continuous",e.Update="update"}(t||(t={})),function(e){e.Point="point",e.Polyline="polyline",e.Polygon="polygon",e.Rectangle="rectangle",e.Circle="circle"}(a||(a={}));var r=o(48993),c=o(74919),d=o.n(c),g=function(e,t){var a={};for(var s in e)Object.prototype.hasOwnProperty.call(e,s)&&t.indexOf(s)<0&&(a[s]=e[s]);if(null!=e&&"function"==typeof Object.getOwnPropertySymbols){var i=0;for(s=Object.getOwnPropertySymbols(e);i<s.length;i++)t.indexOf(s[i])<0&&Object.prototype.propertyIsEnumerable.call(e,s[i])&&(a[s[i]]=e[s[i]])}return a};const p=e=>{const t=window.SVG,{className:a}=e,i=g(e,["className"]),n=(0,s.classNames)("jimu-icon jimu-icon-component",a);return t?s.React.createElement(t,Object.assign({className:n,src:d()},i)):s.React.createElement("svg",Object.assign({className:n},i))};var m=o(86058),u=o.n(m),h=function(e,t){var a={};for(var s in e)Object.prototype.hasOwnProperty.call(e,s)&&t.indexOf(s)<0&&(a[s]=e[s]);if(null!=e&&"function"==typeof Object.getOwnPropertySymbols){var i=0;for(s=Object.getOwnPropertySymbols(e);i<s.length;i++)t.indexOf(s[i])<0&&Object.prototype.propertyIsEnumerable.call(e,s[i])&&(a[s[i]]=e[s[i]])}return a};const f=e=>{const t=window.SVG,{className:a}=e,i=h(e,["className"]),n=(0,s.classNames)("jimu-icon jimu-icon-component",a);return t?s.React.createElement(t,Object.assign({className:n,src:u()},i)):s.React.createElement("svg",Object.assign({className:n},i))};var I=o(42588),w=o.n(I),x=function(e,t){var a={};for(var s in e)Object.prototype.hasOwnProperty.call(e,s)&&t.indexOf(s)<0&&(a[s]=e[s]);if(null!=e&&"function"==typeof Object.getOwnPropertySymbols){var i=0;for(s=Object.getOwnPropertySymbols(e);i<s.length;i++)t.indexOf(s[i])<0&&Object.prototype.propertyIsEnumerable.call(e,s[i])&&(a[s[i]]=e[s[i]])}return a};const M=e=>{const t=window.SVG,{className:a}=e,i=x(e,["className"]),n=(0,s.classNames)("jimu-icon jimu-icon-component",a);return t?s.React.createElement(t,Object.assign({className:n,src:w()},i)):s.React.createElement("svg",Object.assign({className:n},i))};var j=o(2985),b=o.n(j),v=function(e,t){var a={};for(var s in e)Object.prototype.hasOwnProperty.call(e,s)&&t.indexOf(s)<0&&(a[s]=e[s]);if(null!=e&&"function"==typeof Object.getOwnPropertySymbols){var i=0;for(s=Object.getOwnPropertySymbols(e);i<s.length;i++)t.indexOf(s[i])<0&&Object.prototype.propertyIsEnumerable.call(e,s[i])&&(a[s[i]]=e[s[i]])}return a};const S=e=>{const t=window.SVG,{className:a}=e,i=v(e,["className"]),n=(0,s.classNames)("jimu-icon jimu-icon-component",a);return t?s.React.createElement(t,Object.assign({className:n,src:b()},i)):s.React.createElement("svg",Object.assign({className:n},i))};var y=o(60846),N=o.n(y),P=function(e,t){var a={};for(var s in e)Object.prototype.hasOwnProperty.call(e,s)&&t.indexOf(s)<0&&(a[s]=e[s]);if(null!=e&&"function"==typeof Object.getOwnPropertySymbols){var i=0;for(s=Object.getOwnPropertySymbols(e);i<s.length;i++)t.indexOf(s[i])<0&&Object.prototype.propertyIsEnumerable.call(e,s[i])&&(a[s[i]]=e[s[i]])}return a};const D=e=>{const t=window.SVG,{className:a}=e,i=P(e,["className"]),n=(0,s.classNames)("jimu-icon jimu-icon-component",a);return t?s.React.createElement(t,Object.assign({className:n,src:N()},i)):s.React.createElement("svg",Object.assign({className:n},i))},O=s.React.memo((e=>{const t=s.React.useRef(null),i=[{id:a.Point,icon:p,des:e.intl.formatMessage({id:"drawModePoint",defaultMessage:n.defaultMessages.drawModePoint})},{id:a.Polyline,icon:f,des:e.intl.formatMessage({id:"drawModeLine",defaultMessage:n.defaultMessages.drawModeLine})},{id:a.Polygon,icon:M,des:e.intl.formatMessage({id:"drawModePolygon",defaultMessage:n.defaultMessages.drawModePolygon})},{id:a.Rectangle,icon:S,des:e.intl.formatMessage({id:"drawModeRectangle",defaultMessage:n.defaultMessages.drawModeRectangle})},{id:a.Circle,icon:D,des:e.intl.formatMessage({id:"drawModeCircle",defaultMessage:n.defaultMessages.drawModeCircle})}],o=t=>{if(!e.items||!e.items.length)return!1;for(let a=0,s=e.items.length;a<s;a++){if(t===e.items[a])return!0}return!1},l=()=>{r()},r=()=>{const a=[],s=t.current.querySelectorAll("input");for(let e=0,t=s.length;e<t;e++){const t=s[e];t.checked&&a.push(t.getAttribute("data-itemid"))}e.onDrawingToolsChange(a)};return(0,s.jsx)("div",{ref:t,css:(()=>{const t=e.theme;return s.css`
      font-size: 13px;
      font-weight: lighter;
      color: ${t.ref.palette.neutral[1100]};

      .items-option{
        padding: 0;
        margin: 0;
        list-style: none;
        list-style-type: none;
        /*background: ${t.ref.palette.neutral[300]};*/

        .item{
          margin: 6px 0;

          .icon{
            color: ${t.ref.palette.neutral[1e3]};
          }

          .item-label{
            margin: 0;
          }
        }
      }
    `})()},(0,s.jsx)("ul",{className:"items-option",role:"group","aria-label":e.title},(()=>{const e=[];for(let t=0,a=i.length;t<a;t++){const a=i[t],r=o(a.id);e.push((0,s.jsx)("li",{className:"d-flex item",key:"key-"+t},(0,s.jsx)(a.icon,{className:"icon mr-2"}),(0,s.jsx)(n.Label,{className:"d-flex item-label justify-content-between flex-grow-1 text-break","aria-label":a.des},a.des,(0,s.jsx)(n.Switch,{className:"d-flex","data-itemid":a.id,checked:r,onChange:l,"aria-label":a.des}))))}return e})()))})),C=s.React.memo((e=>{const t=s.React.useRef(null),a=(0,r.useMeasurementsUnitsInfos)(),[o,l]=s.React.useState((()=>{const t=[];return a.forEach((a=>{const s=a.value;let i=Object.assign({},a);const n=e.measurementsUnitsInfos.find((e=>e.value===s));n&&(i=Object.assign(Object.assign({},i),n)),t.push(i)})),t})),c=e=>{const t=o.find((t=>t.value===e));return t&&t.actived},d=t=>{const a=o.map((e=>(t===e.value&&(e.actived=!e.actived),e)));l(a),e.onUnitsSettingChange(a)},g=e.intl.formatMessage({id:"drawUnits",defaultMessage:n.defaultMessages.drawUnits});return(0,s.jsx)(i.SettingRow,null,(0,s.jsx)("div",{className:"d-block w-100",role:"group","aria-label":g},(0,s.jsx)(i.SettingRow,{label:g,className:"w-100 mb-2"}),(0,s.jsx)("div",{ref:t,className:"w-100",css:(()=>{const t=e.theme;return s.css`
      font-size: 13px;
      font-weight: lighter;
      width: 100%;
      height: 154px;
      overflow-y: scroll;
      background: ${t.ref.palette.neutral[300]};

      .dotdotdot{
        text-align: left;
        justify-content: start;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .util-iteams{
        list-style: none;
        list-style-type: none;
        /*background: ${t.ref.palette.neutral[300]};*/

        .item{
          margin: 10px 0;
          align-items: center;

          .item-note-wapper{
            /*width: 80px;*/
            .item-note{
              display: inline-block;
              width: 100%;
            }
          }

          .item-label{
            width: 105px;
          }
        }
      }
    `})()},(0,s.jsx)("ul",{className:"util-iteams p-0 mx-2 mb-0",role:"group","aria-label":g},(()=>{const e=[];for(let t=0,a=o.length;t<a;t++){const a=o[t],i=c(a.value),l=a.note;e.push((0,s.jsx)("li",{className:"d-flex item",key:"key-"+t},(0,s.jsx)(n.Checkbox,{className:"d-flex mr-2","data-itemid":a.value,checked:i,onChange:()=>{d(a.value)},"aria-label":l}),(0,s.jsx)("div",{className:"d-flex mr-4 item-note-wapper dotdotdot"},(0,s.jsx)(n.Label,{className:"item-note dotdotdot",title:l,"aria-label":l},l))))}return e})()))))})),R=s.React.memo((e=>{const t=(t,a)=>{let s;switch(a){case"point":s=Object.assign(Object.assign({},e.decimalPlaces),{point:t});break;case"line":s=Object.assign(Object.assign({},e.decimalPlaces),{line:t});break;case"area":s=Object.assign(Object.assign({},e.decimalPlaces),{area:t});break;default:throw new Error}e.onDecimalPlacesChange(s)},a=(0,s.useIntl)().formatMessage({id:"decimalPlaces",defaultMessage:n.defaultMessages.decimalPlaces}),o=(0,s.useIntl)().formatMessage({id:"drawModePoint",defaultMessage:n.defaultMessages.drawModePoint}),l=(0,s.useIntl)().formatMessage({id:"drawModeLine",defaultMessage:n.defaultMessages.drawModeLine}),r=(0,s.useIntl)().formatMessage({id:"drawToolAreaTip",defaultMessage:n.defaultMessages.drawToolAreaTip});return(0,s.jsx)("div",{css:s.css`
      .decimal-title {
        .jimu-widget-setting--row-label{
          max-width: 100%;
        }
      }

      .inputs {
        .jimu-widget-setting--row-label{
          width: auto !important;
          margin-bottom: 0;
        }
        .numeric-input {
          width: 56px;
        }
      }
    `,className:"d-block w-100",role:"group","aria-label":a},(0,s.jsx)(i.SettingRow,{label:a,className:"w-100 mb-2 mt-2 decimal-title bold-font-label"}),(0,s.jsx)("div",{className:"inputs"},(0,s.jsx)(i.SettingRow,{flow:"wrap",label:o,className:"w-100"},(0,s.jsx)(n.NumericInput,{size:"sm",className:"numeric-input","aria-label":o,precision:0,min:0,max:10,value:e.decimalPlaces.point,onChange:e=>{t(e,"point")}})),(0,s.jsx)(i.SettingRow,{flow:"wrap",label:l,className:"w-100 mt-2"},(0,s.jsx)(n.NumericInput,{size:"sm",className:"numeric-input","aria-label":l,precision:0,min:0,max:10,value:e.decimalPlaces.line,onChange:e=>{t(e,"line")}})),(0,s.jsx)(i.SettingRow,{flow:"wrap",label:r,className:"w-100 mt-2"},(0,s.jsx)(n.NumericInput,{size:"sm",className:"numeric-input","aria-label":r,precision:0,min:0,max:10,value:e.decimalPlaces.area,onChange:e=>{t(e,"area")}}))))}));function T(e,t){const a=e.ref.palette.neutral[300],i=e.ref.palette.neutral[1e3];return s.css`
      font-size: 13px;
      font-weight: lighter;

      .jimu-widget-setting--section {
        padding: 18px 16px;
      }

      .ui-mode-setting {
        display: flex;
      }

      /* ui-mode */
      .ui-mode-card-chooser{
        display: flex;
        align-items: start;

        .ui-mode-card-wapper {
          width: calc((100% - ${10}px - ${8}px) / 2);
        }

        .ui-mode-card-separator {
          width: ${10}px
        }
        .ui-mode-card {
          flex: 1;
          width: 100%;
          background: ${a};
          border: ${2}px solid ${a};
          margin: 0 0 0.5rem 0;

          .jimu-icon {
            margin: 0
          }
        }
        .ui-mode-card.active {
          border: ${2}px solid #00D8ED;
          background-color: ${a} !important;
        }
        .ui-mode-label {
          overflow: hidden;
          text-align: center;
        }
      }

      .placeholder-container{
        height: calc(100% - 180px);

        .placeholder{
          flex-direction: column;

          .icon{
            color: var(--ref-palette-neutral-800);
          }
          .hint{
            font-size: ${t.rem(14)};
            font-weight: 500;
            color: var(--ref-palette-neutral-1000);
            max-width: ${t.rem(160)};
          }
        }

      }

      /* UI for #13051 */
      .bold-font-label {
        .jimu-widget-setting--row-label,
        .setting-row-text-level-1 {
          font-weight: 600 !important;
          color: ${i} !important;
        }
      }

  `}const E="Arrangement",B="Panel",k="Toolbar",H="Drawing tools",Z="Enable measurement",Q="3D drawing effect",W="Relative to ground",G="Relative to scene",V="On the ground";var z=o(31027),A=o.n(z),L=function(e,t){var a={};for(var s in e)Object.prototype.hasOwnProperty.call(e,s)&&t.indexOf(s)<0&&(a[s]=e[s]);if(null!=e&&"function"==typeof Object.getOwnPropertySymbols){var i=0;for(s=Object.getOwnPropertySymbols(e);i<s.length;i++)t.indexOf(s[i])<0&&Object.prototype.propertyIsEnumerable.call(e,s[i])&&(a[s[i]]=e[s[i]])}return a};const U=e=>{const t=window.SVG,{className:a}=e,i=L(e,["className"]),n=(0,s.classNames)("jimu-icon jimu-icon-component",a);return t?s.React.createElement(t,Object.assign({className:n,src:A()},i)):s.React.createElement("svg",Object.assign({className:n},i))};class $ extends s.React.PureComponent{constructor(e){var t;super(e),this.handleMapWidgetChange=e=>{const t=!!(null==e?void 0:e[0]);this.setState({isSelectedMap:t}),this.props.onSettingChange({id:this.props.id,useMapWidgetIds:e})},this.handleIsDisplayCanvasLayerChange=()=>{this.props.onSettingChange({id:this.props.id,config:this.props.config.set("isDisplayCanvasLayer",!this.props.config.isDisplayCanvasLayer)})},this.handleArrangementChange=e=>{this.props.onSettingChange({id:this.props.id,config:this.props.config.set("arrangement",e)})},this.handleShowAdvancedSettingClick=()=>{this.setState({isShowAdvancedSetting:!this.state.isShowAdvancedSetting})},this.handleDrawToolsChange=e=>{this.props.onSettingChange({id:this.props.id,config:this.props.config.set("drawingTools",e)})},this.handleIsEnableMeasurementChange=()=>{this.props.onSettingChange({id:this.props.id,config:this.props.config.setIn(["measurementsInfo","enableMeasurements"],!this.props.config.measurementsInfo.enableMeasurements)})},this.handleMeasurementUnitsInfoChange=e=>{this.props.onSettingChange({id:this.props.id,config:this.props.config.set("measurementsUnitsInfos",e)})},this.handleMDecimalChange=e=>{this.props.onSettingChange({id:this.props.id,config:this.props.config.setIn(["measurementsInfo","decimalPlaces"],e)})},this.handleDrawingElevationMode3DChange=e=>{this.props.onSettingChange({id:this.props.id,config:this.props.config.set("drawingElevationMode3D",e)})},this.state={isSelectedMap:!!(null===(t=this.props.useMapWidgetIds)||void 0===t?void 0:t[0]),isShowAdvancedSetting:!1}}render(){var t;const a=this.props.id+"-uimode-description",l=this.props.id+"-uimode-0",c=this.props.id+"-uimode-1",d=this.props.intl.formatMessage({id:"selectMapWidget",defaultMessage:n.defaultMessages.selectMapWidget}),g=this.props.intl.formatMessage({id:"selectMapHint",defaultMessage:n.defaultMessages.selectMapHint}),p=this.props.intl.formatMessage({id:"arrangementTips",defaultMessage:E}),m=this.props.intl.formatMessage({id:"panelTips",defaultMessage:B}),u=this.props.intl.formatMessage({id:"toolbarTips",defaultMessage:k}),h=this.props.intl.formatMessage({id:"advance",defaultMessage:n.defaultMessages.advance}),f=this.props.intl.formatMessage({id:"drawingToolsTips",defaultMessage:H}),I=this.props.intl.formatMessage({id:"isEnableMeasurementsTips",defaultMessage:Z}),w=this.props.intl.formatMessage({id:"drawingElevationMode3DTips",defaultMessage:Q}),x=this.props.intl.formatMessage({id:"relativeToGroundTips",defaultMessage:W}),M=this.props.intl.formatMessage({id:"relativeToSceneTips",defaultMessage:G}),j=this.props.intl.formatMessage({id:"onTheGroundTips",defaultMessage:V});return(0,s.jsx)("div",{css:T(this.props.theme,s.polished),className:"widget-setting-menu jimu-widget-setting"},(0,s.jsx)(i.SettingSection,{title:d,className:(0,s.classNames)("map-selector-section",{"border-0":!this.state.isSelectedMap})},(0,s.jsx)(i.SettingRow,null,(0,s.jsx)(i.MapWidgetSelector,{onSelect:this.handleMapWidgetChange,useMapWidgetIds:this.props.useMapWidgetIds}))),!this.state.isSelectedMap&&(0,s.jsx)("div",{className:"d-flex placeholder-container justify-content-center align-items-center"},(0,s.jsx)("div",{className:"d-flex text-center placeholder justify-content-center align-items-center "},(0,s.jsx)(U,{size:48,className:"d-flex icon mb-2"}),(0,s.jsx)("p",{className:"hint"},g))),this.state.isSelectedMap&&(0,s.jsx)(s.React.Fragment,null,(0,s.jsx)(i.SettingSection,{title:p},(0,s.jsx)(i.SettingRow,{role:"group","aria-label":p},(0,s.jsx)("div",{className:"ui-mode-card-chooser"},(0,s.jsx)(n.Label,{className:"d-flex flex-column ui-mode-card-wapper"},(0,s.jsx)(n.Button,{icon:!0,className:(0,s.classNames)("ui-mode-card",{active:this.props.config.arrangement===e.Panel}),onClick:()=>{this.handleArrangementChange(e.Panel)},"aria-labelledby":l,"aria-describedby":a,title:m},(0,s.jsx)(n.Icon,{width:100,height:72,icon:o(91108),autoFlip:!0})),(0,s.jsx)("div",{id:l,className:"mx-1 text-break ui-mode-label"},m)),(0,s.jsx)("div",{className:"ui-mode-card-separator"}),(0,s.jsx)(n.Label,{className:"d-flex flex-column ui-mode-card-wapper"},(0,s.jsx)(n.Button,{icon:!0,className:(0,s.classNames)("ui-mode-card",{active:this.props.config.arrangement===e.Toolbar}),onClick:()=>{this.handleArrangementChange(e.Toolbar)},"aria-labelledby":c,"aria-describedby":a,title:u},(0,s.jsx)(n.Icon,{width:100,height:72,icon:o(69125),autoFlip:!0})),(0,s.jsx)("div",{id:c,className:"mx-1 text-break ui-mode-label"},u))))),(0,s.jsx)(i.SettingSection,null,(0,s.jsx)(i.SettingCollapse,{label:h,isOpen:this.state.isShowAdvancedSetting,onRequestOpen:this.handleShowAdvancedSettingClick,onRequestClose:this.handleShowAdvancedSettingClick},(0,s.jsx)(s.React.Fragment,null,(0,s.jsx)(i.SettingSection,{title:f,className:"px-0 bold-font-label",role:"group","aria-label":f},(0,s.jsx)(O,{items:this.props.config.drawingTools.asMutable(),theme:this.props.theme,intl:this.props.intl,title:f,onDrawingToolsChange:this.handleDrawToolsChange})),(0,s.jsx)(i.SettingSection,{className:"px-0"},(0,s.jsx)(i.SettingRow,{label:I,className:"bold-font-label"},(0,s.jsx)(n.Switch,{checked:this.props.config.measurementsInfo.enableMeasurements,onChange:this.handleIsEnableMeasurementChange,"aria-label":I})),this.props.config.measurementsInfo.enableMeasurements&&(0,s.jsx)(C,{theme:this.props.theme,intl:this.props.intl,measurementsUnitsInfos:null===(t=this.props.config.measurementsUnitsInfos)||void 0===t?void 0:t.asMutable(),onUnitsSettingChange:this.handleMeasurementUnitsInfoChange}),this.props.config.measurementsInfo.enableMeasurements&&(0,s.jsx)(R,{decimalPlaces:this.props.config.measurementsInfo.decimalPlaces,onDecimalPlacesChange:this.handleMDecimalChange})),(0,s.jsx)(i.SettingSection,{title:w,className:"px-0",role:"group","aria-label":w},(0,s.jsx)(i.SettingRow,{flow:"wrap"},(0,s.jsx)("div",{role:"radiogroup",className:"mb-4"},(0,s.jsx)(n.Label,{className:"d-flex align-items-center",style:{cursor:"pointer"},title:x},(0,s.jsx)(n.Radio,{style:{cursor:"pointer"},className:"m-0 mr-2",title:x,name:"drawingElevationMode3D",onChange:()=>{this.handleDrawingElevationMode3DChange(r.DrawingElevationMode3D.RelativeToGround)},checked:this.props.config.drawingElevationMode3D===r.DrawingElevationMode3D.RelativeToGround}),x),(0,s.jsx)(n.Label,{className:"d-flex align-items-center",style:{cursor:"pointer"},title:M},(0,s.jsx)(n.Radio,{style:{cursor:"pointer"},className:"m-0 mr-2",title:M,name:"drawingElevationMode3D",onChange:()=>{this.handleDrawingElevationMode3DChange(r.DrawingElevationMode3D.RelativeToScene)},checked:this.props.config.drawingElevationMode3D===r.DrawingElevationMode3D.RelativeToScene}),M),(0,s.jsx)(n.Label,{className:"d-flex align-items-center",style:{cursor:"pointer"},title:j},(0,s.jsx)(n.Radio,{style:{cursor:"pointer"},className:"m-0 mr-2",title:j,name:"drawingElevationMode3D",onChange:()=>{this.handleDrawingElevationMode3DChange(r.DrawingElevationMode3D.OnTheGround)},checked:this.props.config.drawingElevationMode3D===r.DrawingElevationMode3D.OnTheGround}),j)))))))))}}function _(e){o.p=e}})(),l})())}}}));