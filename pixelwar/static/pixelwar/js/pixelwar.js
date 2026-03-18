// --- Community modals logic ---
document.addEventListener('DOMContentLoaded', function () {
    // Modal elements
    const modalBackdrop = document.getElementById('modal-backdrop');
    const invitationModal = document.getElementById('invitation-modal');
    const invitationLinkInput = document.getElementById('invitation-link-input');
    const copyInviteLinkBtn = document.getElementById('copy-invite-link-btn');
    const leaveModal = document.getElementById('leave-modal');
    const leaveForm = document.getElementById('leave-community-form');
    const deleteModal = document.getElementById('delete-modal');
    const deleteForm = document.getElementById('delete-community-form');

    function showModal(modal) {
        modalBackdrop.classList.remove('hidden');
        modal.classList.remove('hidden');
    }
    function hideModals() {
        modalBackdrop.classList.add('hidden');
        [invitationModal, leaveModal, deleteModal].forEach(m => m && m.classList.add('hidden'));
    }
    // Invitation link modal
    document.querySelectorAll('.invitation-link-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const url = btn.getAttribute('data-invite-url');
            if (invitationLinkInput) invitationLinkInput.value = url;
            showModal(invitationModal);
        });
    });
    if (copyInviteLinkBtn && invitationLinkInput) {
        copyInviteLinkBtn.addEventListener('click', function () {
            invitationLinkInput.select();
            invitationLinkInput.setSelectionRange(0, 99999);
            document.execCommand('copy');
            copyInviteLinkBtn.textContent = 'Copied!';
            setTimeout(() => { copyInviteLinkBtn.textContent = 'Copy URL'; }, 1200);
        });
    }
    // Leave community modal
    document.querySelectorAll('.leave-community-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const leaveUrl = btn.getAttribute('data-leave-url') || '';
            if (leaveForm) leaveForm.action = leaveUrl;
            showModal(leaveModal);
        });
    });
    // Delete community modal
    document.querySelectorAll('.delete-community-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const deleteUrl = btn.getAttribute('data-delete-url') || '';
            if (deleteForm) deleteForm.action = deleteUrl;
            showModal(deleteModal);
        });
    });
    // Close modals
    document.querySelectorAll('.close-modal-btn').forEach(btn => {
        btn.addEventListener('click', hideModals);
    });
    if (modalBackdrop) {
        modalBackdrop.addEventListener('click', hideModals);
    }
});
(() => {
    const app = document.querySelector('.app');
    if (!app) {
        return;
    }

    let gridSize = Number(app.dataset.gridSize || '200');
    let filledPixels = Number(app.dataset.filledPixels || '0');
    const currentUserKey = String(app.dataset.userKey || '');
    const pixelSnapshotUrl = String(app.dataset.pixelSnapshotUrl || '/api/pixels/');
    const myPixelsUrl = String(app.dataset.myPixelsUrl || '/api/pixels/mine/');
    const pixelUpdateUrl = String(app.dataset.pixelUpdateUrl || '/api/pixels/update/');
    const chatMessagesUrl = String(app.dataset.chatMessagesUrl || '/api/chat/messages/');
    const chatAllMessagesUrl = String(app.dataset.chatAllMessagesUrl || '');
    const chatSendUrl = String(app.dataset.chatSendUrl || '/api/chat/send/');
    const useGroupedChat = app.dataset.chatGrouped === '1';
    const chatDefaultGroup = String(app.dataset.chatDefaultGroup || 'global');
    const pixelsWsUrl = String(app.dataset.pixelsWsUrl || '/ws/pixels/');
    const chatWsUrl = String(app.dataset.chatWsUrl || '/ws/chat/');
    const canvas = document.getElementById('pixelCanvas');
    const pixelOverlay = document.getElementById('pixelOverlay');
    const ctx = canvas.getContext('2d', { alpha: false });
    const overlayCtx = pixelOverlay.getContext('2d');
    const gridMeta = document.getElementById('gridMeta');
    const cooldownBadge = document.getElementById('cooldownBadge');
    const colorPalette = document.getElementById('colorPalette');
    const customColorPicker = document.getElementById('customColorPicker');
    const status = document.getElementById('status');
    const zoomIn = document.getElementById('zoomIn');
    const zoomOut = document.getElementById('zoomOut');
    const resetZoom = document.getElementById('resetZoom');
    const highlightMine = document.getElementById('highlightMine');
    const canvasFullscreen = document.getElementById('canvasFullscreen');
    const chatToggle = document.getElementById('chatToggle');
    const chatPanel = document.getElementById('chatPanel');
    const chatClose = document.getElementById('chatClose');
    const chatMute = document.getElementById('chatMute');
    const chatPin = document.getElementById('chatPin');
    const chatMessages = document.getElementById('chatMessages');
    const chatUnreadBadge = document.getElementById('chatUnreadBadge');
    const chatNotice = document.getElementById('chatNotice');
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const chatGroupsContainer = document.getElementById('chatGroups');
    const chatGroupsDataTag = document.getElementById('chat-groups-data');
    const isAuthenticated = app.dataset.authenticated === '1';
    const canSendChat = app.dataset.chatCanSend === '1';
    const currentUsername = String(app.dataset.currentUsername || '').trim();
    let reconnectDelayMs = 1000;
    let reconnectTimer = null;
    let groupedChatTimer = null;
    let cooldownTimer = null;
    let cooldownRemaining = 0;
    let cooldownUntilTs = 0;
    let isRealtimeConnected = false;
    let hasLoadedSnapshot = false;
    let requestInFlight = false;
    let selectedColor = '#000000';
    let isChatOpen = false;
    let isChatPinned = false;
    let isChatMuted = false;
    let unreadCount = 0;
    let chatNoticeTimer = null;
    let suppressChatSound = true;
    let audioCtx = null;
    let selectedChatGroup = useGroupedChat ? 'global' : chatDefaultGroup;
    let chatHasMoreHistory = true;
    let chatLoadingHistory = false;
    let chatUnreadSeeded = false;
    const chatPageSize = 20;
    let manualZoomLockUntil = 0;
    let didInitialSmartZoom = false;
    let isHighlightingMine = false;
    let minePixelsLoaded = false;
    const minePixels = new Set();
    const knownChatMessageKeys = new Set();
    const chatUnreadByGroup = new Map();
    const cooldownStorageKey = [
        'pixelwar',
        'cooldownUntil',
        pixelUpdateUrl,
        currentUserKey || 'anon',
    ].join(':');

    const chatGroups = (() => {
        if (!chatGroupsDataTag) {
            return [];
        }
        try {
            const parsed = JSON.parse(chatGroupsDataTag.textContent || '[]');
            if (Array.isArray(parsed)) {
                return parsed;
            }
        } catch (_error) {
            // Ignore malformed metadata and fallback to default behavior.
        }
        return [];
    })();
    const chatGroupMap = new Map(chatGroups.map((group) => [group.slug, group]));

    let scale = 1;
    const minScale = 1;
    const maxScale = 24;

    canvas.width = gridSize;
    canvas.height = gridSize;
    pixelOverlay.width = gridSize;
    pixelOverlay.height = gridSize;

    function pixelKey(x, y) {
        return `${x}:${y}`;
    }

    function parsePixelKey(key) {
        const [x, y] = String(key).split(':');
        return { x: Number(x), y: Number(y) };
    }

    function renderMineHighlightMask() {
        overlayCtx.clearRect(0, 0, gridSize, gridSize);
        if (!isHighlightingMine) {
            return;
        }

        overlayCtx.fillStyle = 'rgba(255,255,255,0.2)';
        overlayCtx.fillRect(0, 0, gridSize, gridSize);
        for (const key of minePixels) {
            const point = parsePixelKey(key);
            if (point.x >= 0 && point.y >= 0 && point.x < gridSize && point.y < gridSize) {
                overlayCtx.clearRect(point.x, point.y, 1, 1);
            }
        }
    }

    function updateMineHighlightButton() {
        if (!highlightMine) {
            return;
        }
        if (!isAuthenticated) {
            highlightMine.textContent = 'Highlight My Pixels';
            return;
        }
        highlightMine.textContent = isHighlightingMine
            ? 'Show All Pixels'
            : 'Highlight My Pixels';
        highlightMine.className = isHighlightingMine
            ? 'rounded-xl bg-gradient-to-r from-fuchsia-500 to-pink-500 px-3 py-2 text-sm font-semibold text-white'
            : 'rounded-xl bg-white px-3 py-2 text-sm font-semibold text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50';
    }

    function setHighlightMode(nextValue) {
        isHighlightingMine = Boolean(nextValue);
        updateMineHighlightButton();
        renderMineHighlightMask();
    }

    async function loadMinePixels() {
        if (!isAuthenticated) {
            return;
        }
        const response = await fetch(myPixelsUrl, { cache: 'no-store' });
        if (!response.ok) {
            throw new Error('Failed to load your pixel mask');
        }
        const payload = await response.json();
        minePixels.clear();
        for (const point of payload.pixels || []) {
            if (!Array.isArray(point) || point.length !== 2) {
                continue;
            }
            minePixels.add(pixelKey(Number(point[0]), Number(point[1])));
        }
        minePixelsLoaded = true;
    }

    function updateGridMeta() {
        if (!gridMeta) {
            return;
        }
        const total = gridSize * gridSize;
        const ratio = total > 0 ? Math.round((filledPixels / total) * 100) : 0;
        gridMeta.textContent = `Grid: ${gridSize}x${gridSize}. Filled: ${filledPixels}/${total} (${ratio}%). Scroll on smaller screens.`;
    }

    function setGridSize(nextSize) {
        const parsed = Number(nextSize || 0);
        if (!Number.isFinite(parsed) || parsed < 1) {
            return;
        }
        if (parsed === gridSize) {
            return;
        }
        gridSize = parsed;
        canvas.width = gridSize;
        canvas.height = gridSize;
        pixelOverlay.width = gridSize;
        pixelOverlay.height = gridSize;
        applyScale();
        updateGridMeta();
        renderMineHighlightMask();
    }

    function setStatus(message, mode = 'ok') {
        const cooldownActive = cooldownRemaining > 0 || cooldownUntilTs > Date.now();
        if (cooldownActive && mode === 'ok') {
            return;
        }
        status.textContent = message;
        if (mode === 'error') {
            status.className = 'mt-3 text-sm font-medium text-rose-600';
            return;
        }
        status.className = 'mt-3 text-sm font-medium text-slate-700';
    }

    function setCanvasLocked(locked) {
        canvas.style.pointerEvents = locked ? 'none' : 'auto';
        canvas.style.cursor = locked ? 'not-allowed' : 'crosshair';
    }

    function persistCooldownUntil(value) {
        try {
            window.localStorage.setItem(cooldownStorageKey, String(value));
        } catch (_error) {
            // Ignore browsers/storage modes that block localStorage writes.
        }
    }

    function readPersistedCooldownUntil() {
        try {
            const raw = window.localStorage.getItem(cooldownStorageKey);
            if (!raw) {
                return 0;
            }
            const value = Number(raw);
            if (Number.isFinite(value) && value > 0) {
                return value;
            }
        } catch (_error) {
            // Ignore localStorage read errors and fallback to in-memory timer.
        }
        return 0;
    }

    function clearPersistedCooldown() {
        try {
            window.localStorage.removeItem(cooldownStorageKey);
        } catch (_error) {
            // Ignore localStorage cleanup failures.
        }
    }

    function computeCooldownRemainingSeconds() {
        if (cooldownUntilTs <= 0) {
            return 0;
        }
        return Math.max(0, Math.ceil((cooldownUntilTs - Date.now()) / 1000));
    }

    function updateCooldownUi() {
        cooldownRemaining = computeCooldownRemainingSeconds();
        if (cooldownRemaining <= 0) {
            cooldownUntilTs = 0;
            const shouldLock = !isRealtimeConnected || !hasLoadedSnapshot;
            setCanvasLocked(shouldLock);
            clearPersistedCooldown();
            setStatus('');
            if (cooldownBadge) {
                cooldownBadge.classList.add('hidden');
            }
            if (cooldownTimer) {
                window.clearInterval(cooldownTimer);
                cooldownTimer = null;
            }
            return;
        }
        setCanvasLocked(true);
        if (cooldownBadge) {
            cooldownBadge.textContent = String(cooldownRemaining);
            cooldownBadge.classList.remove('hidden');
        }
    }

    function ensureCooldownTicker() {
        if (cooldownTimer) {
            return;
        }
        cooldownTimer = window.setInterval(() => {
            updateCooldownUi();
        }, 1000);
    }

    function startCooldown(seconds) {
        const nextSeconds = Math.max(0, Number(seconds || 0));
        if (nextSeconds <= 0) {
            cooldownUntilTs = 0;
            updateCooldownUi();
            return;
        }

        cooldownUntilTs = Date.now() + (nextSeconds * 1000);
        persistCooldownUntil(cooldownUntilTs);
        updateCooldownUi();
        ensureCooldownTicker();
    }

    function restoreCooldownFromStorage() {
        const persistedUntil = readPersistedCooldownUntil();
        if (persistedUntil <= 0) {
            return;
        }
        cooldownUntilTs = persistedUntil;
        updateCooldownUi();
        if (computeCooldownRemainingSeconds() > 0) {
            ensureCooldownTicker();
        }
    }

    function applyScale() {
        canvas.style.width = `${gridSize * scale}px`;
        canvas.style.height = `${gridSize * scale}px`;
        pixelOverlay.style.width = `${gridSize * scale}px`;
        pixelOverlay.style.height = `${gridSize * scale}px`;
    }

    function smartScaleForBoard() {
        const total = gridSize * gridSize;
        const ratio = total > 0 ? filledPixels / total : 0;

        let target = 3;
        if (gridSize <= 200) {
            target = 7;
        } else if (gridSize <= 260) {
            target = 6;
        } else if (gridSize <= 340) {
            target = 5;
        } else if (gridSize <= 460) {
            target = 4;
        } else if (gridSize <= 620) {
            target = 3;
        } else {
            target = 2;
        }

        if (ratio > 0.6) {
            target -= 1;
        }
        if (ratio > 0.8) {
            target -= 1;
        }

        return Math.max(minScale, Math.min(maxScale, target));
    }

    function maybeAutoZoom(force = false) {
        if (!force && Date.now() < manualZoomLockUntil) {
            return;
        }
        const target = smartScaleForBoard();
        if (scale !== target) {
            scale = target;
            applyScale();
        }
    }

    function updatePaletteSelection() {
        const buttons = colorPalette.querySelectorAll('button[data-color]');
        buttons.forEach((button) => {
            const active = button.dataset.color.toLowerCase() === selectedColor.toLowerCase();
            button.classList.toggle('ring-2', active);
            button.classList.toggle('ring-fuchsia-500', active);
            button.classList.toggle('ring-offset-2', active);
            button.classList.toggle('ring-offset-white', active);
        });
        if (customColorPicker) {
            customColorPicker.value = selectedColor;
        }
    }

    function drawPixel(x, y, color) {
        ctx.fillStyle = color;
        ctx.fillRect(x, y, 1, 1);
    }

    function avatarFallback(username) {
        if (!username || typeof username !== 'string') {
            return '?';
        }
        return username.charAt(0).toUpperCase();
    }

    function formatTimestamp(value) {
        if (!value) {
            return '';
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return '';
        }
        return date.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
        });
    }

    function setChatNotice(message, mode = 'info') {
        if (!chatNotice) {
            return;
        }
        if (chatNoticeTimer) {
            window.clearTimeout(chatNoticeTimer);
            chatNoticeTimer = null;
        }
        chatNotice.textContent = message;
        if (mode === 'error') {
            chatNotice.className = 'mb-2 min-h-4 text-xs font-medium text-rose-600';
            return;
        }
        chatNotice.className = 'mb-2 min-h-4 text-xs font-medium text-slate-500';

        if (String(message).trim() === 'Message queued') {
            chatNoticeTimer = window.setTimeout(() => {
                setChatNotice('');
            }, 1800);
        }
    }

    function playChatSound() {
        if (suppressChatSound || isChatMuted) {
            return;
        }
        try {
            if (!audioCtx) {
                const AudioContextClass = window.AudioContext || window.webkitAudioContext;
                if (!AudioContextClass) {
                    return;
                }
                audioCtx = new AudioContextClass();
            }

            const now = audioCtx.currentTime;
            const oscLow = audioCtx.createOscillator();
            const oscHigh = audioCtx.createOscillator();
            const gain = audioCtx.createGain();

            oscLow.type = 'sine';
            oscHigh.type = 'triangle';
            oscLow.frequency.setValueAtTime(720, now);
            oscLow.frequency.exponentialRampToValueAtTime(940, now + 0.12);
            oscHigh.frequency.setValueAtTime(980, now + 0.08);
            oscHigh.frequency.exponentialRampToValueAtTime(1240, now + 0.2);
            gain.gain.setValueAtTime(0.0001, now);
            gain.gain.exponentialRampToValueAtTime(0.055, now + 0.03);
            gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.24);

            oscLow.connect(gain);
            oscHigh.connect(gain);
            gain.connect(audioCtx.destination);
            oscLow.start(now);
            oscHigh.start(now + 0.08);
            oscLow.stop(now + 0.18);
            oscHigh.stop(now + 0.25);
        } catch (_error) {
            // Ignore sound playback errors (browser policy or unsupported API).
        }
    }

    function playPixelPlacementSound() {
        try {
            if (!audioCtx) {
                const AudioContextClass = window.AudioContext || window.webkitAudioContext;
                if (!AudioContextClass) {
                    return;
                }
                audioCtx = new AudioContextClass();
            }

            const now = audioCtx.currentTime;
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();

            osc.type = 'triangle';
            osc.frequency.setValueAtTime(560, now);
            osc.frequency.exponentialRampToValueAtTime(430, now + 0.08);
            gain.gain.setValueAtTime(0.0001, now);
            gain.gain.exponentialRampToValueAtTime(0.04, now + 0.01);
            gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.1);

            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.start(now);
            osc.stop(now + 0.1);
        } catch (_error) {
            // Ignore audio playback errors and continue normal flow.
        }
    }

    function setChatPinned(nextPinned) {
        isChatPinned = Boolean(nextPinned);
        chatPanel.classList.toggle('pinned', isChatPinned);
        if (chatPin) {
            chatPin.textContent = isChatPinned ? 'Unpin' : 'Pin';
        }
    }

    function updateMuteButton() {
        if (!chatMute) {
            return;
        }
        chatMute.textContent = isChatMuted ? 'Sound Off' : 'Sound On';
    }

    async function toggleCanvasFullscreen() {
        const container = canvas.parentElement;
        if (!container) {
            return;
        }

        if (!document.fullscreenElement) {
            await container.requestFullscreen();
        } else {
            await document.exitFullscreen();
        }
    }

    function updateFullscreenButton() {
        if (!canvasFullscreen) {
            return;
        }
        const isFull = Boolean(document.fullscreenElement);
        canvasFullscreen.setAttribute('aria-label', isFull ? 'Exit full screen' : 'Full screen');
        canvasFullscreen.setAttribute('title', isFull ? 'Exit full screen' : 'Full screen');
    }

    function renderUnreadBadge() {
        if (!chatUnreadBadge) {
            return;
        }
        if (unreadCount <= 0) {
            chatUnreadBadge.classList.add('hidden');
            return;
        }
        chatUnreadBadge.textContent = String(unreadCount > 99 ? '99+' : unreadCount);
        chatUnreadBadge.classList.remove('hidden');
    }

    function messageGroupSlug(item) {
        if (!useGroupedChat) {
            return chatDefaultGroup;
        }
        return String(item.group_slug || chatDefaultGroup || 'global');
    }

    function recalculateUnreadTotal() {
        let total = 0;
        for (const value of chatUnreadByGroup.values()) {
            total += Number(value || 0);
        }
        unreadCount = total;
        renderUnreadBadge();
    }

    function renderChatGroupUnreadBadges() {
        if (!chatGroupsContainer || !useGroupedChat) {
            return;
        }
        const buttons = chatGroupsContainer.querySelectorAll('[data-chat-group]');
        buttons.forEach((button) => {
            const slug = String(button.dataset.chatGroup || 'global');
            const count = Number(chatUnreadByGroup.get(slug) || 0);
            const badge = button.querySelector('[data-chat-group-unread]');
            if (!badge) {
                return;
            }
            if (count <= 0) {
                badge.classList.add('hidden');
                badge.textContent = '0';
                return;
            }
            badge.classList.remove('hidden');
            badge.textContent = String(count > 99 ? '99+' : count);
        });
    }

    function markGroupAsRead(groupSlug) {
        const slug = String(groupSlug || '');
        if (!slug) {
            return;
        }
        if (!chatUnreadByGroup.has(slug)) {
            return;
        }
        chatUnreadByGroup.set(slug, 0);
        renderChatGroupUnreadBadges();
        recalculateUnreadTotal();
    }

    function incrementUnread(groupSlug, delta) {
        const slug = String(groupSlug || '');
        const add = Number(delta || 0);
        if (!slug || add <= 0) {
            return;
        }
        const current = Number(chatUnreadByGroup.get(slug) || 0);
        chatUnreadByGroup.set(slug, current + add);
    }

    function applyUnreadDeltas(deltaByGroup) {
        for (const [slug, delta] of deltaByGroup.entries()) {
            incrementUnread(slug, delta);
        }
        if (isChatOpen) {
            markGroupAsRead(selectedChatGroup);
        } else {
            renderChatGroupUnreadBadges();
            recalculateUnreadTotal();
        }
    }

    function appendChatMessage(item, options = {}) {
        const silent = Boolean(options.silent);
        const isOwn = (
            Boolean(currentUsername)
            && String(item.username || '').toLowerCase() === currentUsername.toLowerCase()
        );
        const row = document.createElement('div');
        row.className = isOwn
            ? 'mb-2 ml-auto max-w-[88%] rounded-xl bg-fuchsia-50 px-2.5 py-2'
            : 'mb-2 mr-auto max-w-[88%] rounded-xl bg-slate-50 px-2.5 py-2';

        const header = document.createElement('div');
        header.className = isOwn
            ? 'mb-1 flex items-center justify-end gap-2'
            : 'mb-1 flex items-center gap-2';

        let avatarElement = null;
        if (item.avatar_url) {
            const img = document.createElement('img');
            img.src = item.avatar_url;
            img.alt = 'avatar';
            img.className = 'h-7 w-7 rounded-full object-cover';
            avatarElement = img;
        } else {
            const avatar = document.createElement('div');
            avatar.className = 'flex h-7 w-7 items-center justify-center rounded-full bg-fuchsia-500 text-xs font-bold text-white';
            avatar.textContent = avatarFallback(item.username);
            avatarElement = avatar;
        }

        const title = document.createElement('div');
        title.className = 'text-xs font-semibold text-slate-700';
        title.textContent = item.username || 'User';
        header.appendChild(avatarElement);
        header.appendChild(title);

        if (useGroupedChat && item.group_name) {
            const groupBadge = document.createElement('span');
            groupBadge.className = 'rounded-full bg-fuchsia-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-fuchsia-700';
            groupBadge.textContent = item.group_name;
            header.appendChild(groupBadge);
        }

        const timestamp = document.createElement('div');
        timestamp.className = 'ml-auto text-[10px] text-slate-400';
        timestamp.textContent = formatTimestamp(item.created_at);
        header.appendChild(timestamp);

        const body = document.createElement('p');
        body.className = isOwn
            ? 'text-right text-sm text-slate-800 break-words'
            : 'text-sm text-slate-800 break-words';
        body.textContent = item.message || '';

        row.appendChild(header);
        row.appendChild(body);
        chatMessages.appendChild(row);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        if (!silent) {
            playChatSound();
        }
    }

    function messageKey(item) {
        if (item && item.id !== undefined && item.id !== null) {
            return `id:${item.id}`;
        }
        return `raw:${item.username || ''}:${item.created_at || ''}:${item.message || ''}`;
    }

    function shouldShowMessage(item) {
        if (!useGroupedChat) {
            return true;
        }
        if (!item.group_slug) {
            return true;
        }
        return String(item.group_slug || '') === selectedChatGroup;
    }

    function renderChatMessages(items, options = {}) {
        const silent = Boolean(options.silent);
        chatMessages.innerHTML = '';
        for (const item of items) {
            if (!shouldShowMessage(item)) {
                continue;
            }
            appendChatMessage(item, { silent });
        }
    }

    function updateChatGroupButtons() {
        if (!chatGroupsContainer) {
            return;
        }
        const buttons = chatGroupsContainer.querySelectorAll('[data-chat-group]');
        buttons.forEach((button) => {
            const isActive = button.dataset.chatGroup === selectedChatGroup;
            button.classList.toggle('active', isActive);
        });
    }

    function renderChatGroupTabs() {
        if (!useGroupedChat || !chatGroupsContainer) {
            return;
        }
        const groupButtons = chatGroups.map((group) => (
            `<button type="button" data-chat-group="${group.slug}" `
            + 'class="chat-group-tab">'
            + `<span>${group.name}</span>`
            + '<span data-chat-group-unread '
            + 'class="chat-group-unread hidden">0</span>'
            + '</button>'
        ));
        chatGroupsContainer.innerHTML = groupButtons.join('');
        updateChatGroupButtons();
        renderChatGroupUnreadBadges();
    }

    function currentChatSendUrl() {
        if (!useGroupedChat) {
            return chatSendUrl;
        }
        const targetGroup = chatGroupMap.get(selectedChatGroup);
        if (targetGroup && targetGroup.send_url) {
            return String(targetGroup.send_url);
        }
        return chatSendUrl;
    }

    function currentChatMessagesUrl() {
        if (!useGroupedChat) {
            return chatMessagesUrl;
        }
        const targetGroup = chatGroupMap.get(selectedChatGroup);
        if (targetGroup && targetGroup.messages_url) {
            return String(targetGroup.messages_url);
        }
        return chatMessagesUrl;
    }

    function chatPageUrl(baseUrl, offset, limit) {
        const target = new URL(baseUrl, window.location.origin);
        target.searchParams.set('offset', String(Math.max(0, offset)));
        target.searchParams.set('limit', String(Math.max(1, limit)));
        return target.toString();
    }

    async function fetchChatPage(baseUrl, offset, limit) {
        const response = await fetch(chatPageUrl(baseUrl, offset, limit), {
            cache: 'no-store',
        });
        if (!response.ok) {
            return { messages: [], hasMore: false };
        }
        const payload = await response.json();
        const messages = Array.isArray(payload.messages) ? payload.messages : [];
        const hasMore = Boolean(payload.has_more);
        return { messages, hasMore };
    }

    function isChatNearBottom() {
        const threshold = 40;
        return (
            chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight
        ) <= threshold;
    }

    async function loadLatestChatPage(options = {}) {
        const silent = Boolean(options.silent);
        const keepBottom = Boolean(options.keepBottom);
        const page = await fetchChatPage(currentChatMessagesUrl(), 0, chatPageSize);
        renderChatMessages(page.messages, { silent });
        chatHasMoreHistory = page.hasMore;
        if (keepBottom) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    async function loadOlderChatPage() {
        if (chatLoadingHistory || !chatHasMoreHistory) {
            return;
        }
        chatLoadingHistory = true;
        const previousHeight = chatMessages.scrollHeight;
        const currentCount = chatMessages.children.length;
        const page = await fetchChatPage(
            currentChatMessagesUrl(),
            currentCount,
            chatPageSize,
        );
        if (!page.messages.length) {
            chatHasMoreHistory = false;
            chatLoadingHistory = false;
            return;
        }
        const fragment = document.createDocumentFragment();
        for (const message of page.messages) {
            const rowBefore = chatMessages.children.length;
            appendChatMessage(message, { silent: true });
            const row = chatMessages.lastElementChild;
            if (row && rowBefore >= 0) {
                fragment.appendChild(row);
            }
        }
        chatMessages.insertBefore(fragment, chatMessages.firstChild);
        chatHasMoreHistory = page.hasMore;
        const nextHeight = chatMessages.scrollHeight;
        chatMessages.scrollTop = nextHeight - previousHeight;
        chatLoadingHistory = false;
    }

    async function syncUnreadCounts() {
        const sourceUrl = (useGroupedChat && chatAllMessagesUrl)
            ? chatAllMessagesUrl
            : chatMessagesUrl;
        const page = await fetchChatPage(sourceUrl, 0, 80);
        const messages = page.messages;
        const deltaByGroup = new Map();
        const nextKeys = new Set();

        for (const item of messages) {
            const key = messageKey(item);
            nextKeys.add(key);
            if (chatUnreadSeeded && !knownChatMessageKeys.has(key)) {
                const slug = messageGroupSlug(item);
                deltaByGroup.set(slug, Number(deltaByGroup.get(slug) || 0) + 1);
            }
        }

        knownChatMessageKeys.clear();
        for (const key of nextKeys) {
            knownChatMessageKeys.add(key);
        }

        if (!chatUnreadSeeded) {
            chatUnreadSeeded = true;
            return;
        }

        if (deltaByGroup.size > 0) {
            applyUnreadDeltas(deltaByGroup);
            if (!suppressChatSound) {
                playChatSound();
            }
        }
        suppressChatSound = false;
    }

    async function sendChatMessage(message) {
        const csrfToken = getCookie('csrftoken');
        const response = await fetch(currentChatSendUrl(), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({ message }),
        });

        if (response.ok) {
            setChatNotice('Message queued', 'info');
            return true;
        }

        if (response.status === 429) {
            const info = await response.json();
            setChatNotice(`Slow down. Try again in ${info.retry_after}s`, 'error');
            return false;
        }

        if (response.status === 401) {
            setChatNotice('Please log in to send messages.', 'error');
            window.location.href = '/auth/login/';
            return false;
        }

        if (response.status === 403) {
            return false;
        }

        const text = await response.text();
        setChatNotice(`Send failed: ${text}`, 'error');
        return false;
    }

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) {
            return parts.pop().split(';').shift();
        }
        return '';
    }

    function clientToGrid(event) {
        const rect = canvas.getBoundingClientRect();
        const x = Math.floor(((event.clientX - rect.left) / rect.width) * gridSize);
        const y = Math.floor(((event.clientY - rect.top) / rect.height) * gridSize);
        return { x, y };
    }

    async function loadSnapshot(options = {}) {
        const applySmartZoom = Boolean(options.applySmartZoom);
        const response = await fetch(pixelSnapshotUrl, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to load initial snapshot');
        }

        const payload = await response.json();
        filledPixels = Number(payload.filled_pixels || payload.pixels.length || 0);
        hasLoadedSnapshot = true;
        setGridSize(Number(payload.grid_size || gridSize));
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, gridSize, gridSize);

        for (const pixel of payload.pixels) {
            drawPixel(pixel.x, pixel.y, pixel.color);
        }

        updateGridMeta();
        renderMineHighlightMask();
        if (applySmartZoom && !didInitialSmartZoom) {
            maybeAutoZoom(true);
            didInitialSmartZoom = true;
        }
        setStatus(`Loaded ${payload.pixels.length} pixels on ${gridSize}x${gridSize}`);
    }

    async function sendPixel(x, y, color) {
        const csrfToken = getCookie('csrftoken');
        const response = await fetch(pixelUpdateUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({ x, y, color }),
        });

        if (response.ok) {
            const info = await response.json();
            const nextGridSize = Number(info.grid_size);
            const gridChanged = Number.isFinite(nextGridSize) && nextGridSize !== gridSize;
            if (gridChanged) {
                await loadSnapshot();
            }
            if (Number.isFinite(Number(info.filled_pixels))) {
                filledPixels = Number(info.filled_pixels);
                updateGridMeta();
            }
            return {
                ok: true,
                cooldown: Number(info.cooldown_seconds || 60),
            };
        }

        if (response.status === 429) {
            const info = await response.json();
            startCooldown(Number(info.retry_after || 0));
            return {
                ok: false,
            };
        }

        if (response.status === 302 || response.status === 401) {
            setStatus('Please log in to place a pixel.', 'error');
            window.location.href = '/auth/login/';
            return {
                ok: false,
            };
        }

        if (response.status === 403) {
            setStatus('You no longer have access to this community.', 'error');
            window.location.href = '/';
            return {
                ok: false,
            };
        }

        const text = await response.text();
        setStatus(`Update failed: ${text}`, 'error');
        return {
            ok: false,
        };
    }

    function connectWebsocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const socket = new WebSocket(
            `${protocol}://${window.location.host}${pixelsWsUrl}`
        );

        socket.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data);
                if (payload.x >= gridSize || payload.y >= gridSize) {
                    loadSnapshot().catch(() => {});
                    return;
                }
                drawPixel(payload.x, payload.y, payload.color);
                const key = pixelKey(payload.x, payload.y);
                if (payload.user_key && currentUserKey) {
                    if (payload.user_key === currentUserKey) {
                        minePixels.add(key);
                    } else {
                        minePixels.delete(key);
                    }
                    if (isHighlightingMine) {
                        renderMineHighlightMask();
                    }
                }
            } catch (error) {
                setStatus('Realtime update parse error', 'error');
            }
        };

        socket.onopen = () => {
            reconnectDelayMs = 1000;
            isRealtimeConnected = true;
            updateCooldownUi();
        };
        socket.onclose = () => {
            isRealtimeConnected = false;
            setCanvasLocked(true);
            if (reconnectTimer) {
                window.clearTimeout(reconnectTimer);
            }
            reconnectTimer = window.setTimeout(() => {
                connectWebsocket();
            }, reconnectDelayMs);
            reconnectDelayMs = Math.min(reconnectDelayMs * 2, 10000);
        };
    }

    function connectChatWebsocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const socket = new WebSocket(
            `${protocol}://${window.location.host}${chatWsUrl}`
        );

        socket.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data);
                const key = messageKey(payload);
                if (knownChatMessageKeys.has(key)) {
                    return;
                }
                knownChatMessageKeys.add(key);
                appendChatMessage(payload);
                const groupSlug = messageGroupSlug(payload);
                if (isChatOpen && groupSlug === selectedChatGroup) {
                    markGroupAsRead(groupSlug);
                } else {
                    const deltaByGroup = new Map([[groupSlug, 1]]);
                    applyUnreadDeltas(deltaByGroup);
                }
            } catch (_error) {
                // Ignore malformed chat events to avoid breaking the UI loop.
            }
        };

        socket.onclose = () => {
            window.setTimeout(() => {
                connectChatWebsocket();
            }, 2000);
        };
    }

    canvas.addEventListener('click', async (event) => {
        if (!isRealtimeConnected || !hasLoadedSnapshot) {
            setCanvasLocked(true);
            return;
        }
        if (requestInFlight || cooldownRemaining > 0) {
            if (cooldownRemaining > 0) {
                updateCooldownUi();
            }
            return;
        }

        const { x, y } = clientToGrid(event);
        if (x < 0 || y < 0 || x >= gridSize || y >= gridSize) {
            return;
        }

        requestInFlight = true;
        playPixelPlacementSound();

        try {
            const result = await sendPixel(x, y, selectedColor);
            if (result && result.ok) {
                drawPixel(x, y, selectedColor);
                startCooldown(result.cooldown);
            }
        } catch (error) {
            setStatus('Network error while sending pixel', 'error');
        } finally {
            requestInFlight = false;
        }
    });

    if (zoomIn) {
        zoomIn.addEventListener('click', () => {
            manualZoomLockUntil = Date.now() + 20000;
            scale = Math.min(maxScale, scale + 1);
            applyScale();
        });
    }

    if (zoomOut) {
        zoomOut.addEventListener('click', () => {
            manualZoomLockUntil = Date.now() + 20000;
            scale = Math.max(minScale, scale - 1);
            applyScale();
        });
    }

    if (resetZoom) {
        resetZoom.addEventListener('click', () => {
            manualZoomLockUntil = Date.now() + 20000;
            scale = smartScaleForBoard();
            applyScale();
        });
    }

    if (canvasFullscreen) {
        canvasFullscreen.addEventListener('click', () => {
            toggleCanvasFullscreen().catch(() => {});
        });
    }

    if (highlightMine) {
        highlightMine.addEventListener('click', async () => {
            if (!isAuthenticated) {
                setStatus('Please log in to use personal pixel highlight.', 'error');
                window.location.href = '/auth/login/';
                return;
            }

            if (!isHighlightingMine && !minePixelsLoaded) {
                try {
                    await loadMinePixels();
                } catch (_error) {
                    setStatus('Could not load your pixels right now.', 'error');
                    return;
                }
            }
            setHighlightMode(!isHighlightingMine);
        });
    }

    document.addEventListener('fullscreenchange', () => {
        updateFullscreenButton();
    });

    colorPalette.addEventListener('click', (event) => {
        const target = event.target.closest('button[data-color]');
        if (!target) {
            return;
        }
        selectedColor = target.dataset.color;
        updatePaletteSelection();
    });

    if (customColorPicker) {
        customColorPicker.addEventListener('input', () => {
            selectedColor = customColorPicker.value;
            updatePaletteSelection();
        });
    }

    applyScale();
    updatePaletteSelection();
    updateGridMeta();
    updateMineHighlightButton();
    setCanvasLocked(true);
    restoreCooldownFromStorage();
    loadSnapshot({ applySmartZoom: true })
        .then(() => {
            connectWebsocket();
            updateCooldownUi();
        })
        .catch((error) => {
            setStatus(error.message, 'error');
        });
    if (useGroupedChat) {
        for (const group of chatGroups) {
            chatUnreadByGroup.set(group.slug, 0);
        }
        renderChatGroupTabs();
        loadLatestChatPage({ silent: true, keepBottom: true }).catch(() => {});
        syncUnreadCounts().catch(() => {});
        groupedChatTimer = window.setInterval(() => {
            const shouldKeepBottom = isChatOpen && isChatNearBottom();
            syncUnreadCounts().catch(() => {});
            if (shouldKeepBottom) {
                loadLatestChatPage({
                    silent: true,
                    keepBottom: true,
                }).catch(() => {});
            }
        }, 4000);
    } else {
        chatUnreadByGroup.set(chatDefaultGroup, 0);
        loadLatestChatPage({ silent: true, keepBottom: true }).catch(() => {});
        connectChatWebsocket();
    }

    chatMessages.addEventListener('scroll', () => {
        if (chatMessages.scrollTop > 16) {
            return;
        }
        loadOlderChatPage().catch(() => {});
    });

    chatToggle.addEventListener('click', () => {
        chatPanel.classList.remove('hidden');
        isChatOpen = true;
        loadLatestChatPage({ silent: true, keepBottom: true }).catch(() => {});
        if (useGroupedChat) {
            markGroupAsRead(selectedChatGroup);
        } else {
            markGroupAsRead(chatDefaultGroup);
        }
    });

    if (chatGroupsContainer && useGroupedChat) {
        chatGroupsContainer.addEventListener('click', (event) => {
            const button = event.target.closest('[data-chat-group]');
            if (!button) {
                return;
            }
            const nextGroup = String(button.dataset.chatGroup || 'all');
            if (selectedChatGroup === nextGroup) {
                return;
            }
            selectedChatGroup = nextGroup;
            updateChatGroupButtons();
            markGroupAsRead(selectedChatGroup);
            loadLatestChatPage({ silent: true, keepBottom: true }).catch(() => {});
        });
    }

    chatClose.addEventListener('click', () => {
        chatPanel.classList.add('hidden');
        isChatOpen = false;
    });

    chatPin.addEventListener('click', () => {
        setChatPinned(!isChatPinned);
        if (isChatPinned) {
            chatPanel.classList.remove('hidden');
            isChatOpen = true;
        }
    });

    chatMute.addEventListener('click', () => {
        isChatMuted = !isChatMuted;
        updateMuteButton();
    });

    if (chatForm && isAuthenticated) {
        chatForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (!canSendChat) {
                return;
            }
            const text = chatInput.value.trim();
            if (!text) {
                return;
            }
            const sent = await sendChatMessage(text);
            if (sent) {
                chatInput.value = '';
            }
        });
    }

    renderUnreadBadge();
    setChatPinned(false);
    updateMuteButton();
    updateFullscreenButton();

    window.addEventListener('storage', (event) => {
        if (event.key !== cooldownStorageKey) {
            return;
        }
        cooldownUntilTs = readPersistedCooldownUntil();
        updateCooldownUi();
        if (computeCooldownRemainingSeconds() > 0) {
            ensureCooldownTicker();
        }
    });
})();
