// Keep the native Tauri app intact; use the browser studio when opened in a normal browser.
if ("__TAURI_INTERNALS__" in window) {
  void import("./main");
} else {
  void import("./web-app");
}
