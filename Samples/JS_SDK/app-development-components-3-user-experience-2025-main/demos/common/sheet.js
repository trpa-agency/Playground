export default `<calcite-sheet id="sheet" display-mode="float" width-scale="m">
<calcite-panel
  heading="Esri Developer & Technology Summit"
  description="Helpful conference links"
  closable
  id="sheet-panel"
>
  <calcite-menu
    layout="vertical"
    label="2025 Esri Developer & Technology Summit Menu"
  >
    <calcite-menu-item
      text="2025 Esri Developer & Technology Summit Overview"
      icon-end="launch"
      href="https://www.esri.com/en-us/about/events/devsummit/overview"
      target="_blank"
    ></calcite-menu-item>
    <calcite-menu-item
      text="Esri Developer Events GitHub"
      icon-end="launch"
      href="https://github.com/EsriDevEvents"
      target="_blank"
    ></calcite-menu-item>
    <calcite-menu-item
      text="Esri.com"
      icon-end="launch"
      href="https://esri.com"
      target="_blank"
    ></calcite-menu-item>
  </calcite-menu>
  <calcite-notice open slot="footer" width="full" scale="s">
    <span slot="title">Note</span>
    <span slot="message"
      >This is a demonstration application showcasing platform
      functionality. While Esri strives to ensure the sample is accurate,
      it may not reflect implementation behavior in certain
      environments.</span
    >
  </calcite-notice>
</calcite-panel>
</calcite-sheet>`;
