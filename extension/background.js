/**
 * Emote Audio Studio - Background Service Worker (Manifest V3)
 * Handles Roblox session detection, group discovery, Open Cloud upload, and asset polling.
 */

const ROBLOX_API_BASE = "https://apis.roblox.com/assets/v1";

// Cache for session info
let cachedUser = null;
let cachedGroups = [];

// Helper: Get active Roblox authenticated user
async function getRobloxUser() {
  try {
    const res = await fetch("https://users.roblox.com/v1/users/authenticated", {
      credentials: "include"
    });
    if (!res.ok) {
      cachedUser = null;
      return null;
    }
    const data = await res.json();
    cachedUser = {
      id: data.id,
      name: data.name,
      displayName: data.displayName
    };
    return cachedUser;
  } catch (err) {
    console.warn("[EAS Extension] Failed to check Roblox session:", err);
    return null;
  }
}

// Helper: Get user's groups
async function getRobloxGroups(userId) {
  try {
    if (!userId) {
      const user = await getRobloxUser();
      if (!user) return [];
      userId = user.id;
    }
    const res = await fetch(`https://groups.roblox.com/v1/users/${userId}/groups/roles`, {
      credentials: "include"
    });
    if (!res.ok) return [];
    const data = await res.json();
    cachedGroups = (data.data || []).map(g => ({
      id: g.group.id,
      name: g.group.name,
      role: g.role.name,
      rank: g.role.rank
    }));
    return cachedGroups;
  } catch (err) {
    console.warn("[EAS Extension] Failed to fetch groups:", err);
    return [];
  }
}

// Helper: Open Cloud Upload
async function uploadToRobloxOpenCloud({ apiKey, groupId, name, fileBase64, mimeType = "audio/wav" }) {
  if (!apiKey) throw new Error("API Key Roblox tidak boleh kosong.");
  if (!groupId) throw new Error("Group ID tidak boleh kosong.");

  // Convert base64 to Uint8Array
  const byteChars = atob(fileBase64.split(",")[1] || fileBase64);
  const byteNumbers = new Array(byteChars.length);
  for (let i = 0; i < byteChars.length; i++) {
    byteNumbers[i] = byteChars.charCodeAt(i);
  }
  const byteArray = new Uint8Array(byteNumbers);

  const boundary = "----WebKitFormBoundary" + Math.random().toString(36).substring(2);
  const metadata = {
    assetType: "Audio",
    displayName: (name || "Audio").substring(0, 50),
    description: "Uploaded via Emote Audio Studio Extension",
    creationContext: {
      creator: {
        groupId: String(groupId)
      }
    }
  };

  const metaHeader = `--${boundary}\r\nContent-Disposition: form-data; name="request"\r\nContent-Type: application/json\r\n\r\n${JSON.stringify(metadata)}\r\n`;
  const fileHeader = `--${boundary}\r\nContent-Disposition: form-data; name="fileContent"; filename="${(name || "audio")}.wav"\r\nContent-Type: ${mimeType}\r\n\r\n`;
  const footer = `\r\n--${boundary}--\r\n`;

  const enc = new TextEncoder();
  const metaBytes = enc.encode(metaHeader);
  const fileHeaderBytes = enc.encode(fileHeader);
  const footerBytes = enc.encode(footer);

  const totalLength = metaBytes.length + fileHeaderBytes.length + byteArray.length + footerBytes.length;
  const combined = new Uint8Array(totalLength);
  let offset = 0;
  combined.set(metaBytes, offset); offset += metaBytes.length;
  combined.set(fileHeaderBytes, offset); offset += fileHeaderBytes.length;
  combined.set(byteArray, offset); offset += byteArray.length;
  combined.set(footerBytes, offset);

  const res = await fetch(`${ROBLOX_API_BASE}/assets`, {
    method: "POST",
    headers: {
      "x-api-key": apiKey,
      "Content-Type": `multipart/form-data; boundary=${boundary}`
    },
    body: combined
  });

  if (!res.ok) {
    const errText = await res.text();
    let errMsg = errText;
    try {
      const errJson = JSON.parse(errText);
      errMsg = errJson.message || errText;
    } catch (_) {}
    throw new Error(`Roblox Upload Gagal (${res.status}): ${errMsg}`);
  }

  const resJson = await res.json();
  const path = resJson.path || "";
  const operationId = path.split("/").pop();
  if (!operationId) throw new Error("Roblox tidak mengembalikan operation id.");

  return { operationId, name };
}

// Poll operation status
async function pollOperationStatus(apiKey, operationId, maxAttempts = 40) {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, 3000));
    const res = await fetch(`${ROBLOX_API_BASE}/operations/${operationId}`, {
      headers: { "x-api-key": apiKey }
    });
    if (!res.ok) continue;
    const data = await res.json();
    if (data.done) {
      if (data.error) {
        throw new Error(data.error.message || "Roblox menolak aset audio.");
      }
      const assetId = data.response?.assetId;
      if (!assetId) throw new Error("Asset ID tidak ditemukan pada respon sukses.");

      // Save to recent
      saveRecentAsset({
        assetId: String(assetId),
        timestamp: Date.now()
      });

      return { done: true, assetId: String(assetId) };
    }
  }
  return { done: false, error: "Waktu tunggu habis (masih diproses moderasi Roblox)." };
}

// Save recent asset to storage
async function saveRecentAsset(item) {
  try {
    const { recent_assets = [] } = await chrome.storage.local.get("recent_assets");
    const updated = [item, ...recent_assets.filter(a => a.assetId !== item.assetId)].slice(0, 30);
    await chrome.storage.local.set({ recent_assets: updated });
    
    // Broadcast to any open EAS tabs
    const tabs = await chrome.tabs.query({});
    for (const tab of tabs) {
      if (tab.id) {
        chrome.tabs.sendMessage(tab.id, {
          action: "EAS_NEW_ASSET_DETECTED",
          asset: item
        }).catch(() => {});
      }
    }
  } catch (err) {
    console.warn("Storage save failed:", err);
  }
}

// Message Listener from Popup or Content Scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "GET_ROBLOX_STATUS") {
    (async () => {
      const user = await getRobloxUser();
      const groups = user ? await getRobloxGroups(user.id) : [];
      sendResponse({ user, groups });
    })();
    return true; // Keep channel open for async response
  }

  if (request.action === "UPLOAD_AUDIO") {
    (async () => {
      try {
        const { operationId, name } = await uploadToRobloxOpenCloud(request.payload);
        sendResponse({ success: true, operationId, name });
      } catch (err) {
        sendResponse({ success: false, error: err.message });
      }
    })();
    return true;
  }

  if (request.action === "POLL_STATUS") {
    (async () => {
      try {
        const result = await pollOperationStatus(request.apiKey, request.operationId);
        sendResponse({ success: true, result });
      } catch (err) {
        sendResponse({ success: false, error: err.message });
      }
    })();
    return true;
  }

  if (request.action === "RECORD_DETECTED_ASSET") {
    saveRecentAsset(request.asset);
    sendResponse({ success: true });
    return false;
  }
});

