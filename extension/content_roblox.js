/**
 * Emote Audio Studio - Content Script for Roblox Creator Dashboard
 * Detects Audio Asset IDs on create.roblox.com and injects quick copy/export buttons.
 */

(function () {
  console.log("[EAS Extension] Roblox Creator Dashboard Monitor Loaded");

  // Style injection for smooth Apple Glass pills
  const style = document.createElement("style");
  style.textContent = `
    .eas-pill-btn {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      margin-left: 8px;
      padding: 3px 10px;
      border-radius: 980px;
      background: rgba(0, 113, 227, 0.85);
      color: #ffffff !important;
      font-size: 11px;
      font-weight: 600;
      border: 1px solid rgba(255, 255, 255, 0.35);
      backdrop-filter: blur(10px);
      cursor: pointer;
      box-shadow: 0 4px 12px rgba(0, 113, 227, 0.25);
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      z-index: 100;
    }
    .eas-pill-btn:hover {
      background: rgba(0, 119, 237, 1);
      transform: translateY(-1px) scale(1.02);
      box-shadow: 0 6px 16px rgba(0, 113, 227, 0.4);
    }
    .eas-pill-btn:active {
      transform: scale(0.97);
    }
    .eas-toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      padding: 12px 20px;
      border-radius: 16px;
      background: rgba(28, 28, 30, 0.92);
      color: #ffffff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 13px;
      font-weight: 600;
      box-shadow: 0 16px 40px rgba(0, 0, 0, 0.4);
      border: 1px solid rgba(255, 255, 255, 0.15);
      backdrop-filter: blur(20px);
      z-index: 999999;
      display: flex;
      align-items: center;
      gap: 8px;
      animation: easFadeIn 0.3s ease;
    }
    @keyframes easFadeIn {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }
  `;
  document.head.appendChild(style);

  function showToast(text) {
    const existing = document.querySelector(".eas-toast");
    if (existing) existing.remove();

    const toast = document.createElement("div");
    toast.className = "eas-toast";
    toast.innerHTML = `<span>🎵</span> <span>${text}</span>`;
    document.body.appendChild(toast);
    setTimeout(() => {
      toast.style.transition = "opacity 0.3s ease";
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 2500);
  }

  // Scan for asset ID elements
  function scanAndEnhance() {
    // 1. URLs like .../marketplace/1234567890/configure
    const links = document.querySelectorAll('a[href*="/marketplace/"], a[href*="/asset/"]');
    links.forEach(a => {
      if (a.dataset.easProcessed) return;
      const match = a.href.match(/(?:marketplace|asset)\/(\d+)/);
      if (match && match[1]) {
        a.dataset.easProcessed = "true";
        const assetId = match[1];

        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "eas-pill-btn";
        btn.innerHTML = `🎵 Salin ID (${assetId})`;
        btn.title = "Salin rbxassetid ke Clipboard & Simpan di EAS";
        btn.onclick = (e) => {
          e.preventDefault();
          e.stopPropagation();
          navigator.clipboard.writeText(assetId);
          showToast(`Asset ID ${assetId} tersalin!`);

          // Send to background
          chrome.runtime.sendMessage({
            action: "RECORD_DETECTED_ASSET",
            asset: {
              assetId: assetId,
              name: a.innerText || "Audio Roblox",
              timestamp: Date.now()
            }
          });
        };
        a.parentNode.insertBefore(btn, a.nextSibling);
      }
    });

    // 2. Also check current URL if we are on a configure page
    const curMatch = window.location.pathname.match(/(?:marketplace|creations)\/(\d+)/);
    if (curMatch && curMatch[1]) {
      const assetId = curMatch[1];
      if (!window.__eas_last_recorded || window.__eas_last_recorded !== assetId) {
        window.__eas_last_recorded = assetId;
        chrome.runtime.sendMessage({
          action: "RECORD_DETECTED_ASSET",
          asset: {
            assetId: assetId,
            name: document.title || "Audio Roblox",
            timestamp: Date.now()
          }
        });
      }
    }
  }

  // MutationObserver to catch client-side rendered routes (React/Next.js dashboard)
  const observer = new MutationObserver(() => {
    scanAndEnhance();
  });

  observer.observe(document.body, { childList: true, subtree: true });
  scanAndEnhance();
})();

