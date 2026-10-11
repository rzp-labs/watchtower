import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";

const source = readFileSync(new URL("../librarymanager.js", import.meta.url), "utf8");
function components(React, libraries) {
  const start = source.indexOf("  function createUiComponents(");
  assert.notEqual(start, -1);
  const end = source.indexOf("  const PLUGIN_ID", start);
  return Function("React", `${source.slice(start, end)}; return createUiComponents;`)(React)(libraries);
}

const mockReact = {
  createElement: (type, props, ...children) => ({ type, props, children }),
  createContext: () => ({ Provider: "Provider" }),
  useContext: () => null
};

test("upstream Stash keeps its existing Bootstrap component instances", () => {
  const Bootstrap = { Button: {}, Modal: {}, Form: {} };
  assert.equal(components(mockReact, { Bootstrap }), Bootstrap);
});

test("MUI-only hosts map Watchtower button and modal semantics without modifying PluginApi", () => {
  const libraries = { MUI: { Button: "Button", Dialog: "Dialog" } };
  const { Button, Modal } = components(mockReact, libraries);
  const clicked = () => {};
  const button = Button({ variant: "danger", size: "sm", disabled: true, onClick: clicked });
  assert.equal(button.type, "Button");
  assert.equal(button.props.color, "error");
  assert.equal(button.props.size, "small");
  assert.equal(button.props.disabled, true);
  assert.equal(button.props.onClick, clicked);
  const outline = Button({ variant: "outline-warning" });
  assert.equal(outline.props.variant, "outlined");
  assert.equal(outline.props.color, "warning");
  let hidden = 0;
  const modal = Modal({ show: true, size: "xl", onHide: () => hidden++, backdrop: "static", keyboard: false, enforceFocus: false }).children[0];
  assert.equal(modal.type, "Dialog");
  assert.equal(modal.props.open, true);
  assert.equal(modal.props.maxWidth, "xl");
  assert.equal(modal.props.disableEnforceFocus, true);
  modal.props.onClose({}, "backdropClick");
  modal.props.onClose({}, "escapeKeyDown");
  assert.equal(hidden, 0);
  Modal({ show: true, onHide: () => hidden++ }).children[0].props.onClose({}, "escapeKeyDown");
  assert.equal(hidden, 1);
  assert.equal(libraries.Bootstrap, undefined);
});

// Use the consuming app's existing React/MUI/jsdom dependencies; no browser,
// running Stash instance, package installation or production calls are needed.
const dependencies = process.env.WATCHTOWER_TEST_DEPENDENCIES;
test("real React17/MUI controls handle disabled clicks, fields and repeated modal open/close", { skip: !dependencies, timeout: 15000 }, async () => {
  const require = createRequire(`${dependencies}/package.json`);
  const { JSDOM } = require("jsdom");
  const dom = new JSDOM("<!doctype html><html><body></body></html>", { url: "https://example.test", pretendToBeVisual: true });
  const keys = ["window", "document", "HTMLElement", "Element", "Node", "DocumentFragment", "getComputedStyle", "MessageChannel"];
  const previous = Object.fromEntries(keys.map(key => [key, globalThis[key]]));
  keys.forEach(key => { globalThis[key] = typeof dom.window[key] === "function" && key === "getComputedStyle" ? dom.window[key].bind(dom.window) : dom.window[key]; });
  const React = require("react");
  const MUI = Object.fromEntries(["Button", "Dialog", "DialogTitle", "IconButton", "Typography", "DialogContent", "DialogActions", "FormControl", "FormLabel", "TextField"].map(name => [name, require(`@mui/material/${name}`).default]));
  const { render, fireEvent, cleanup, waitFor } = require("@testing-library/react");
  const { Button, Modal, Form } = components(React, { MUI });
  try {
    let clicks = 0;
    const button = render(React.createElement(Button, { disabled: true, onClick: () => clicks++ }, "Apply"));
    fireEvent.click(button.getByRole("button", { name: "Apply" }));
    assert.equal(clicks, 0);
    button.rerender(React.createElement(Button, { onClick: () => clicks++ }, "Apply"));
    fireEvent.click(button.getByRole("button", { name: "Apply" }));
    assert.equal(clicks, 1);
    button.unmount();
    let value = "";
    const field = render(React.createElement(Form.Group, null,
      React.createElement(Form.Label, { htmlFor: "test-filename" }, "Filename"),
      React.createElement(Form.Control, { id: "test-filename", defaultValue: "old.mp4", onChange: event => { value = event.target.value; } })));
    fireEvent.change(field.getByLabelText("Filename"), { target: { value: "new.mp4" } });
    assert.equal(value, "new.mp4");
    field.unmount();
    let hides = 0;
    const dialog = show => React.createElement(Modal, { show, onHide: () => hides++, TransitionProps: { timeout: 0 } },
      React.createElement(Modal.Header, { closeButton: true }, React.createElement(Modal.Title, null, "Review")),
      React.createElement(Modal.Body, null, "Body"), React.createElement(Modal.Footer, null, "Footer"));
    const view = render(dialog(true));
    assert.ok(view.getByRole("dialog"));
    fireEvent.click(view.getByRole("button", { name: "Close" }));
    assert.equal(hides, 1);
    view.rerender(dialog(false));
    await waitFor(() => assert.equal(Boolean(document.querySelector("[role=dialog]")), false));
    view.rerender(dialog(true));
    assert.ok(view.getByRole("dialog"));
    fireEvent.keyDown(view.getByRole("dialog"), { key: "Escape", code: "Escape" });
    assert.equal(hides, 2);
    view.unmount();
    assert.equal(Boolean(document.querySelector("[role=dialog]")), false);
  } finally {
    cleanup();
    dom.window.close();
    keys.forEach(key => { globalThis[key] = previous[key]; });
  }
});
