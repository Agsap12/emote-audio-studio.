/**
 * Emote Audio Studio - Popup Script
 */

document.addEventListener("DOMContentLoaded", async () => {
  const robloxStatus = document.getElementById("robloxStatus");
  const userInfo = document.getElementById("userInfo");
  const notLogged = document.getElementById("notLogged");
  const groupBox = document.getElementById("groupBox");
  const groupSelect = document.getElementById("groupSelect");
  const btnApplyGroup = document.getElementById("btnApplyGroup");
  const userName = document.getElementById("userName");
  const userId = document.getElementById("userId");
  const assetList = document.getElementById("assetList");
  const btnClearHistory = document.getElementById("btnClearHistory");
  const btnOpenWeb = document.getElementById("btnOpenWeb");

  // Check Roblox Session
  chrome.runtime.sendMessage({ action: "GET_ROBLOX_STATUS" }, (response) => {
    if (!response || !response.user) {
      robloxStatus.textContent = "Belum Login";
      robloxStatus.className = "badge offline";
      userInfo.style.display = "none";
      groupBox.style.display = "none";
      notLogged.style.display = "block";
      return;
    }

    const { user, groups } = response;
    robloxStatus.textContent = "Terhubung";
    robloxStatus.className = "badge online";
    userName.textContent = user.displayName ? `${user.displayName} (@${user.name})` : user.name;
    userId.textContent = `User ID: ${user.id}`;
    userInfo.style.display = "flex";
    notLogged.style.display = "none";

    if (groups && groups.length > 0) {
      groupBox.style.display = "block";
      groupSelect.innerHTML = "";
      groups.forEach((g) => {
        const opt = document.createElement("option");
        opt.value = g.id;
        opt.textContent = `${g.name} (ID: ${g.id}) - ${g.role}`;
        groupSelect.appendChild(opt);
      });
    } else {
      groupBox.style.display = "none";
    }
  });

  // Apply Group to active EAS tab or save to storage
  btnApplyGroup.addEventListener("click", async () => {
    const selectedGroupId = groupSelect.value;
    if (!selectedGroupId) return;

    await chrome.storage.local.set({ default_group_id: selectedGroupId });

    // Try sending to current tab if it's EAS
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tabs[0]?.id) {
      chrome.tabs.sendMessage(tabs[0].id, {
        action: "EAS_SET_GROUP_ID",
        groupId: selectedGroupId
      }).catch(() => {});
    }

    const originalText = btnApplyGroup.textContent;
    btnApplyGroup.textContent = "Tersimpan ✓";
    setTimeout(() => {
      btnApplyGroup.textContent = originalText;
    }, 1500);
  });

  // Render recent detected assets
  async function renderAssets() {
    const { recent_assets = [] } = await chrome.storage.local.get("recent_assets");
    if (!recent_assets.length) {
      assetList.innerHTML = '<div class="empty-state">Belum ada ID terdeteksi.</div>';
      return;
    }

    assetList.innerHTML = "";
    recent_assets.forEach((item) => {
      const row = document.createElement("div");
      row.className = "asset-item";

      const left = document.createElement("div");
      left.innerHTML = `<b>${item.name || "Audio Roblox"}</b><small>ID: ${item.assetId}</small>`;

      const actions = document.createElement("div");
      actions.className = "asset-actions";

      const btnCopy = document.createElement("button");
      btnCopy.className = "btn sm";
      btnCopy.textContent = "Salin";
      btnCopy.onclick = () => {
        navigator.clipboard.writeText(item.assetId);
        btnCopy.textContent = "✓";
        setTimeout(() => (btnCopy.textContent = "Salin"), 1200);
      };

      const btnOpen = document.createElement("a");
      btnOpen.className = "btn main sm";
      btnOpen.textContent = "Buka";
      btnOpen.href = `https://create.roblox.com/dashboard/creations/marketplace/${item.assetId}/configure`;
      btnOpen.target = "_blank";

      actions.append(btnCopy, btnOpen);
      row.append(left, actions);
      assetList.appendChild(row);
    });
  }

  btnClearHistory.addEventListener("click", async () => {
    await chrome.storage.local.remove("recent_assets");
    renderAssets();
  });

  btnOpenWeb.addEventListener("click", () => {
    chrome.tabs.create({ url: "http://127.0.0.1:8765/" });
  });

  renderAssets();
});

