import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";

// A fresh process/document keeps Emotion's cache attached to this fixture.
const source = readFileSync(new URL("../librarymanager.js", import.meta.url), "utf8");
const dependencies = process.env.WATCHTOWER_TEST_DEPENDENCIES;

test("actual filename correction flow inherits host theme across its body portal and navigation", { skip: !dependencies, timeout: 15000 }, async () => {
  const require = createRequire(`${dependencies}/package.json`);
  const { JSDOM } = require("jsdom");
  const dom = new JSDOM("<!doctype html><html><body></body></html>", { url: "https://example.test/scenes/123", pretendToBeVisual: true });
  const keys = ["window", "document", "HTMLElement", "Element", "Node", "DocumentFragment", "getComputedStyle", "MessageChannel", "MutationObserver", "CustomEvent", "fetch"];
  const previous = Object.fromEntries(keys.map(key => [key, globalThis[key]]));
  keys.forEach(key => { globalThis[key] = key === "getComputedStyle" ? dom.window[key].bind(dom.window) : dom.window[key]; });
  const React = require("react");
  const ReactDOM = require("react-dom");
  const { ThemeProvider, createTheme } = require("@mui/material/styles");
  const MUI = Object.fromEntries(["Button", "Dialog", "DialogTitle", "IconButton", "Typography", "DialogContent", "DialogActions", "FormControl", "FormLabel", "TextField"].map(name => [name, require(`@mui/material/${name}`).default]));
  const { render, fireEvent, cleanup, waitFor, act } = require("@testing-library/react");
  const settings = { autoStartMonitor: false, incomingSettleMinutes: 5, onboardingCompleted: true };
  const calls = [];
  globalThis.fetch = async (_url, options) => {
    const { query, variables } = JSON.parse(options.body);
    calls.push({ query, variables });
    let data;
    if (query.includes("query Config")) data = { configuration: { plugins: { librarymanager: settings } } };
    else if (query.includes("query CorrectionScene")) data = { findScene: { files: [{ id: "1", basename: "old.mp4", path: "/fixture/old.mp4" }] } };
    else if (variables?.args?.mode === "preview_manual_filename") data = { runPluginOperation: { status: "ready", proposed_path: "/fixture/new.mp4", reason: "Fixture preview" } };
    else if (variables?.args?.mode === "apply_manual_filename") data = { runPluginOperation: { status: "renamed", proposed_path: "/fixture/new.mp4" } };
    else data = { runPluginOperation: { state: "stopped", inventory: {}, incoming: {}, pending_events: 0 } };
    return { json: async () => ({ data }) };
  };
  // The menu observer is unrelated to modal/theme behavior; avoid delayed
  // synthetic menu work and keep this fixture completely offline.
  globalThis.MutationObserver = class { observe() {} disconnect() {} };
  let patch;
  window.PluginApi = {
    React, ReactDOM,
    libraries: { MUI, ReactRouterDOM: { NavLink: ({ children }) => React.createElement("span", null, children) } },
    register: { route: () => {} },
    patch: { before: (_name, fn) => { patch = fn; } }
  };
  const themes = [
    createTheme({ palette: { mode: "dark", text: { primary: "#d1fae5", secondary: "#a7f3d0" } } }),
    createTheme({ palette: { mode: "dark", text: { primary: "#e0f2fe", secondary: "#bae6fd" } } })
  ];
  let view;
  const separateRoot = () => document.getElementById("librarymanager-correction-root");
  const host = (theme, mounted = true) => React.createElement(ThemeProvider, { theme },
    mounted ? React.createElement(React.Fragment, null, patch({ children: null })[0].children) : null);
  try {
    await act(async () => { Function(source)(); });
    assert.equal(typeof patch, "function");
    view = render(host(themes[0]));
    await act(async () => { window.StashLibraryManager.openFilenameCorrection("123"); });
    await waitFor(() => assert.equal(document.getElementById("librarymanager-correct-filename")?.value, "old.mp4"));
    const input = document.getElementById("librarymanager-correct-filename");
    const label = document.querySelector('label[for="librarymanager-correct-filename"]');
    assert.equal(getComputedStyle(input).color, "rgb(209, 250, 229)");
    assert.equal(getComputedStyle(label).color, "rgb(167, 243, 208)");
    fireEvent.change(input, { target: { value: "new.mp4" } });
    fireEvent.click(view.getByRole("button", { name: "Preview", exact: true }));
    await waitFor(() => assert.equal(view.getByRole("button", { name: "Apply Correction" }).disabled, false));
    assert.equal(calls.find(call => call.variables?.args?.mode === "preview_manual_filename").variables.args.filename, "new.mp4");
    view.rerender(host(themes[1]));
    await waitFor(() => assert.equal(getComputedStyle(input).color, "rgb(224, 242, 254)"));
    assert.equal(getComputedStyle(label).color, "rgb(186, 230, 253)");
    fireEvent.click(view.getAllByRole("button", { name: "Close", exact: true })[0]);
    await waitFor(() => assert.equal(Boolean(document.querySelector("[role=dialog]")), false));
    await act(async () => { window.StashLibraryManager.openFilenameCorrection("123"); });
    await waitFor(() => assert.equal(document.getElementById("librarymanager-correct-filename")?.value, "old.mp4"));
    view.rerender(host(themes[1], false));
    await waitFor(() => assert.equal(Boolean(document.querySelector("[role=dialog]")), false));
    assert.equal(separateRoot().childElementCount, 0);
    await act(async () => { window.StashLibraryManager.openFilenameCorrection("123"); });
    assert.equal(Boolean(document.querySelector("[role=dialog]")), false);
    view.rerender(host(themes[0]));
    assert.equal(Boolean(document.querySelector("[role=dialog]")), false);
    await act(async () => { window.StashLibraryManager.openFilenameCorrection("123"); });
    await waitFor(() => assert.equal(document.getElementById("librarymanager-correct-filename")?.value, "old.mp4"));
    assert.equal(getComputedStyle(document.getElementById("librarymanager-correct-filename")).color, "rgb(209, 250, 229)");
    fireEvent.change(document.getElementById("librarymanager-correct-filename"), { target: { value: "new.mp4" } });
    fireEvent.click(view.getByRole("button", { name: "Preview", exact: true }));
    await waitFor(() => assert.equal(view.getByRole("button", { name: "Apply Correction" }).disabled, false));
    fireEvent.click(view.getByRole("button", { name: "Apply Correction" }));
    await waitFor(() => assert.equal(Boolean(document.querySelector("[role=dialog]")), false));
    assert.equal(calls.find(call => call.variables?.args?.mode === "apply_manual_filename").variables.args.filename, "new.mp4");
  } finally {
    view?.unmount();
    if (separateRoot()) await act(async () => { ReactDOM.unmountComponentAtNode(separateRoot()); });
    cleanup();
    dom.window.close();
    keys.forEach(key => { globalThis[key] = previous[key]; });
  }
});
