/**
 * Emote Audio Studio - Content Script for EAS Web App
 * Bridges Index.HTML with the Chrome Extension (Roblox Session, Groups, Direct Upload)
 */

(function () {
  console.log("[EAS Extension] Web App Bridge Initialized");

  // Notify page that extension is installed & ready
  function notifyReady() {
    window.postMessage({
      source: "EAS_EXTENSION",
      type: "EXTENSION_READY",
      version: "1.0.0"
    }, "*");
  }

  // Periodic ping in case Index.HTML loads after content script
  notifyReady();
  window.addEventListener("DOMContentLoaded", notifyReady);
  setTimeout(notifyReady, 500);
  setTimeout(notifyReady, 1500);

  // Listen to messages from Index.HTML
  window.addEventListener("message", async (event) => {
    if (event.source !== window || !event.data || event.data.source !== "EAS_PAGE") {
      return;
    }

    const { type, payload, callbackId } = event.data;

    if (type === "PING_EXTENSION") {
      window.postMessage({
        source: "EAS_EXTENSION",
        type: "PONG_EXTENSION",
        callbackId,
        installed: true
      }, "*");
      return;
    }

    if (type === "GET_ROBLOX_STATUS") {
      chrome.runtime.sendMessage({ action: "GET_ROBLOX_STATUS" }, (response) => {
        window.postMessage({
          source: "EAS_EXTENSION",
          type: "ROBLOX_STATUS_RESPONSE",
          callbackId,
          data: response || {}
        }, "*");
      });
      return;
    }

    if (type === "UPLOAD_AUDIO") {
      chrome.runtime.sendMessage({
        action: "UPLOAD_AUDIO",
        payload
      }, (response) => {
        window.postMessage({
          source: "EAS_EXTENSION",
          type: "UPLOAD_AUDIO_RESPONSE",
          callbackId,
          data: response
        }, "*");
      });
      return;
    }

    if (type === "POLL_STATUS") {
      chrome.runtime.sendMessage({
        action: "POLL_STATUS",
        apiKey: payload.apiKey,
        operationId: payload.operationId
      }, (response) => {
        window.postMessage({
          source: "EAS_EXTENSION",
          type: "POLL_STATUS_RESPONSE",
          callbackId,
          data: response
        }, "*");
      });
      return;
    }
  });

  // Listen to messages from background service worker
  chrome.runtime.onMessage.addListener((message) => {
    if (message.action === "EAS_NEW_ASSET_DETECTED") {
      window.postMessage({
        source: "EAS_EXTENSION",
        type: "ASSET_DETECTED",
        asset: message.asset
      }, "*");
    }
  });
})();

