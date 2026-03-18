(() => {
    function byId(id) {
        return document.getElementById(id);
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function visualMarkup(notification, sizeClass, initialsClass, statusClass) {
        const initials = escapeHtml(notification.initials || 'PC');
        const imageUrl = String(notification.image_url || '');
        const visualType = String(notification.visual_type || 'system');
        const bgClass = visualType === 'community'
            ? 'bg-gradient-to-br from-cyan-500 to-sky-500'
            : visualType === 'user'
                ? 'bg-gradient-to-br from-fuchsia-500 to-pink-500'
                : 'bg-gradient-to-br from-slate-700 to-slate-900';
        const content = imageUrl
            ? `<img src="${escapeHtml(imageUrl)}" alt="visual" class="${sizeClass} rounded-full object-cover ring-1 ring-slate-200">`
            : `<div class="flex ${sizeClass} items-center justify-center rounded-full ${initialsClass} font-black text-white ${bgClass}">${initials}</div>`;
        return `
            <div class="relative shrink-0">
                ${content}
                <div class="notification-status-dot absolute -bottom-0.5 -right-0.5 ${statusClass} rounded-full ring-2 ring-white ${notification.is_read ? 'bg-slate-200' : 'bg-fuchsia-500'}"></div>
            </div>
        `;
    }

    function wrapNotification(content, href) {
        if (href) {
            return `<a href="${href}" ${content.anchorAttrs}>${content.inner}</a>`;
        }
        return `<div ${content.anchorAttrs}>${content.inner}</div>`;
    }

    function renderNotification(notification, openPattern) {
        const href = notification.target_url
            ? openPattern.replace(/0\/$/, `${notification.id}/`)
            : '';
        const unreadClass = notification.is_read
            ? 'border-slate-200 bg-white'
            : 'border-fuchsia-200 bg-fuchsia-50/60';
        const unreadDot = notification.is_read
            ? ''
            : '<span class="notification-unread-dot h-2 w-2 rounded-full bg-fuchsia-500"></span>';
        return wrapNotification({
            anchorAttrs: `class="notification-item flex items-start gap-3 rounded-xl border px-3 py-2 ${href ? 'transition hover:border-fuchsia-200 hover:bg-fuchsia-50/70 ' : ''}${unreadClass}" data-notification-id="${notification.id}"`,
            inner: `
                ${visualMarkup(notification, 'h-10 w-10', 'text-xs', 'h-3 w-3')}
                <div class="min-w-0 flex-1">
                    <div class="flex items-center justify-between gap-3">
                        <p class="truncate text-sm font-bold text-slate-900">${escapeHtml(notification.title)}</p>
                        <span class="shrink-0 text-[11px] font-semibold text-slate-400">${escapeHtml(notification.created_at_label)}</span>
                    </div>
                    <p class="mt-1 text-xs text-slate-600">${escapeHtml(notification.body)}</p>
                    <div class="mt-1 flex items-center gap-2 text-[11px] font-semibold text-fuchsia-700">
                        ${unreadDot}
                    </div>
                </div>
            `,
        }, href);
    }

    function renderPageNotification(notification, openPattern) {
        const href = notification.target_url
            ? openPattern.replace(/0\/$/, `${notification.id}/`)
            : '';
        const unreadClass = notification.is_read
            ? 'border-slate-200 bg-white'
            : 'border-fuchsia-200 bg-fuchsia-50/60';
        const unreadDot = notification.is_read
            ? ''
            : '<span class="notification-unread-dot h-2.5 w-2.5 rounded-full bg-fuchsia-500"></span>';
        return wrapNotification({
            anchorAttrs: `class="notification-page-item flex items-start justify-between gap-4 rounded-2xl border px-4 py-3 shadow-sm ${href ? 'transition hover:-translate-y-0.5 hover:shadow-md ' : ''}${unreadClass}" data-notification-id="${notification.id}"`,
            inner: `
                <div class="flex min-w-0 flex-1 items-start gap-3">
                    ${visualMarkup(notification, 'h-12 w-12', 'text-sm', 'h-3.5 w-3.5')}
                    <div class="flex items-center gap-2">
                        <p class="truncate text-sm font-black text-slate-900">${escapeHtml(notification.title)}</p>
                        ${unreadDot}
                    </div>
                    <p class="mt-1 text-sm text-slate-600">${escapeHtml(notification.body)}</p>
                </div>
                <span class="shrink-0 text-xs font-semibold text-slate-400">${escapeHtml(notification.created_at_label)}</span>
            `,
        }, href);
    }

    function setUnreadCount(count) {
        const badge = byId('notification-unread-badge');
        if (!badge) {
            return;
        }
        if (count > 0) {
            badge.textContent = String(count);
            badge.classList.remove('hidden');
        } else {
            badge.textContent = '0';
            badge.classList.add('hidden');
        }
    }

    function updatePageUnreadCount(count) {
        const pageCount = byId('notifications-page-unread-count');
        if (!pageCount) {
            return;
        }
        pageCount.textContent = `${count} unread`;
    }

    function playNotificationSound(audioState) {
        if (!audioState.context) {
            return;
        }
        const oscillator = audioState.context.createOscillator();
        const gain = audioState.context.createGain();
        oscillator.type = 'sine';
        oscillator.frequency.value = 880;
        gain.gain.value = 0.0001;
        oscillator.connect(gain);
        gain.connect(audioState.context.destination);
        const now = audioState.context.currentTime;
        gain.gain.exponentialRampToValueAtTime(0.04, now + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.18);
        oscillator.start(now);
        oscillator.stop(now + 0.2);
    }

    document.addEventListener('DOMContentLoaded', () => {
        const center = byId('notification-center');
        if (!center) {
            return;
        }

        const list = byId('notification-dropdown-list');
        const emptyState = byId('notification-dropdown-empty');
        const pageList = byId('notifications-page-list');
        const pageEmpty = byId('notifications-page-empty');
        const openPattern = String(center.dataset.openPattern || '');
        const wsPath = String(center.dataset.wsPath || '');
        const unreadCount = parseInt(center.dataset.initialUnreadCount || '0', 10) || 0;
        const audioState = { context: null };

        setUnreadCount(unreadCount);
        updatePageUnreadCount(unreadCount);

        const unlockAudio = () => {
            if (!audioState.context) {
                const AudioCtx = window.AudioContext || window.webkitAudioContext;
                if (AudioCtx) {
                    audioState.context = new AudioCtx();
                }
            }
            if (audioState.context && audioState.context.state === 'suspended') {
                audioState.context.resume();
            }
        };

        window.addEventListener('pointerdown', unlockAudio, { once: true });
        window.addEventListener('keydown', unlockAudio, { once: true });

        if (!wsPath || !openPattern) {
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const socket = new WebSocket(`${protocol}//${window.location.host}${wsPath}`);

        socket.addEventListener('message', (event) => {
            let payload;
            try {
                payload = JSON.parse(event.data);
            } catch (_error) {
                return;
            }

            if (typeof payload.unread_count === 'number') {
                setUnreadCount(payload.unread_count);
                updatePageUnreadCount(payload.unread_count);
            }

            if (payload.event === 'notification.created' && payload.notification) {
                if (list) {
                    list.insertAdjacentHTML(
                        'afterbegin',
                        renderNotification(payload.notification, openPattern),
                    );
                    while (list.children.length > 10) {
                        list.removeChild(list.lastElementChild);
                    }
                }
                if (emptyState) {
                    emptyState.classList.add('hidden');
                }
                if (pageList) {
                    pageList.insertAdjacentHTML(
                        'afterbegin',
                        renderPageNotification(payload.notification, openPattern),
                    );
                }
                if (pageEmpty) {
                    pageEmpty.classList.add('hidden');
                }
                unlockAudio();
                playNotificationSound(audioState);
                return;
            }

            if (payload.event === 'notification.read' && payload.notification_id) {
                document
                    .querySelectorAll(`[data-notification-id="${payload.notification_id}"]`)
                    .forEach((item) => {
                        item.classList.remove('border-fuchsia-200', 'bg-fuchsia-50/60');
                        item.classList.add('border-slate-200', 'bg-white');
                        item.querySelectorAll('.notification-status-dot').forEach((dot) => {
                            dot.classList.remove('bg-fuchsia-500');
                            dot.classList.add('bg-slate-200');
                        });
                        item.querySelectorAll('.notification-unread-dot').forEach((dot) => {
                            dot.remove();
                        });
                    });
                return;
            }

            if (payload.event === 'notification.read_all') {
                document.querySelectorAll('.notification-unread-dot').forEach((dot) => {
                    dot.remove();
                });
                document.querySelectorAll('[data-notification-id]').forEach((item) => {
                    item.classList.remove('border-fuchsia-200', 'bg-fuchsia-50/60');
                    item.classList.add('border-slate-200', 'bg-white');
                    item.querySelectorAll('.notification-status-dot').forEach((dot) => {
                        dot.classList.remove('bg-fuchsia-500');
                        dot.classList.add('bg-slate-200');
                    });
                });
            }
        });
    });
})();
