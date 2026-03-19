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
                ? 'bg-gradient-to-br from-emerald-500 to-sky-500'
                : 'bg-gradient-to-br from-emerald-500 to-sky-500';
        const content = imageUrl
            ? `<img src="${escapeHtml(imageUrl)}" alt="visual" class="${sizeClass} rounded-full object-cover ring-1 ring-slate-200">`
            : `<div class="flex ${sizeClass} items-center justify-center rounded-full ${initialsClass} font-black text-white ${bgClass}">${initials}</div>`;
        return `
            <div class="relative shrink-0">
                ${content}
                <div class="notification-status-dot absolute -bottom-0.5 -right-0.5 ${statusClass} rounded-full ring-2 ring-white ${notification.is_read ? 'bg-slate-200' : 'bg-emerald-500'}"></div>
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
            : 'border-emerald-200 bg-emerald-50/60';
        const unreadDot = notification.is_read
            ? ''
            : '<span class="notification-unread-dot h-2 w-2 rounded-full bg-emerald-500"></span>';
        return wrapNotification({
            anchorAttrs: `class="notification-item flex items-start gap-3 rounded-xl border px-3 py-2 ${href ? 'transition hover:border-emerald-200 hover:bg-emerald-50/70 ' : ''}${unreadClass}" data-notification-id="${notification.id}"`,
            inner: `
                ${visualMarkup(notification, 'h-10 w-10', 'text-xs', 'h-3 w-3')}
                <div class="min-w-0 flex-1">
                    <div class="flex flex-col gap-0.5 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                        <p class="text-sm font-bold text-slate-900 break-words sm:truncate">${escapeHtml(notification.title)}</p>
                        <span class="text-[11px] font-semibold text-slate-400 sm:shrink-0">${escapeHtml(notification.created_at_label)}</span>
                    </div>
                    <p class="mt-1 break-words text-xs text-slate-600">${escapeHtml(notification.body)}</p>
                    <div class="mt-1 flex items-center gap-2 text-[11px] font-semibold text-emerald-700">
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
            : 'border-emerald-200 bg-emerald-50/60';
        const unreadDot = notification.is_read
            ? ''
            : '<span class="notification-unread-dot h-2.5 w-2.5 rounded-full bg-emerald-500"></span>';
        return wrapNotification({
            anchorAttrs: `class="notification-page-item flex flex-col gap-2 rounded-2xl border px-4 py-3 shadow-sm sm:flex-row sm:items-start sm:justify-between sm:gap-4 ${href ? 'transition hover:-translate-y-0.5 hover:shadow-md ' : ''}${unreadClass}" data-notification-id="${notification.id}"`,
            inner: `
                <div class="flex min-w-0 flex-1 items-start gap-3">
                    ${visualMarkup(notification, 'h-12 w-12', 'text-sm', 'h-3.5 w-3.5')}
                    <div class="min-w-0 flex-1">
                        <div class="flex items-center gap-2">
                            <p class="truncate text-sm font-black text-slate-900">${escapeHtml(notification.title)}</p>
                            ${unreadDot}
                        </div>
                        <p class="mt-1 break-words text-sm text-slate-600">${escapeHtml(notification.body)}</p>
                    </div>
                </div>
                <span class="self-end text-xs font-semibold text-slate-400 sm:self-auto sm:shrink-0">${escapeHtml(notification.created_at_label)}</span>
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

        // On mobile, reposition the dropdown panel to span the full viewport width
        const dropdown = center.querySelector(':scope > div');
        function positionDropdown() {
            if (!dropdown) return;
            if (window.innerWidth < 640 && center.open) {
                const rect = center.getBoundingClientRect();
                dropdown.style.position = 'fixed';
                dropdown.style.top = (rect.bottom + 2) + 'px';
                dropdown.style.left = '8px';
                dropdown.style.right = '8px';
                dropdown.style.width = 'auto';
                dropdown.style.maxWidth = 'none';
            } else {
                dropdown.style.position = '';
                dropdown.style.top = '';
                dropdown.style.left = '';
                dropdown.style.right = '';
                dropdown.style.width = '';
                dropdown.style.maxWidth = '';
            }
        }
        center.addEventListener('toggle', positionDropdown);
        window.addEventListener('resize', positionDropdown);

        // Mark notification as read when its link is clicked
        center.addEventListener('click', (event) => {
            const item = event.target.closest('[data-notification-id]');
            if (!item) return;
            // Only act if it was unread
            if (!item.classList.contains('border-emerald-200')) return;
            const notifId = item.dataset.notificationId;
            item.classList.remove('border-emerald-200', 'bg-emerald-50/60');
            item.classList.add('border-slate-200', 'bg-white');
            item.querySelectorAll('.notification-status-dot').forEach((dot) => {
                dot.classList.remove('bg-emerald-500');
                dot.classList.add('bg-slate-200');
            });
            item.querySelectorAll('.notification-unread-dot').forEach((dot) => dot.remove());
            // Decrement badge
            const badge = byId('notification-unread-badge');
            if (badge && !badge.classList.contains('hidden')) {
                const current = parseInt(badge.textContent, 10) || 0;
                const next = Math.max(0, current - 1);
                if (next === 0) {
                    badge.classList.add('hidden');
                } else {
                    badge.textContent = String(next);
                }
            }
            // For no-link notifications (div, not anchor) the server is never called
            // via open_notification, so POST to the mark-read endpoint directly.
            if (item.tagName !== 'A') {
                const csrfToken = (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || '';
                fetch(`/notifications/mark/${encodeURIComponent(notifId)}/`, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest' },
                    credentials: 'same-origin',
                });
            }
        });

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
                        item.classList.remove('border-emerald-200', 'bg-emerald-50/60');
                        item.classList.add('border-slate-200', 'bg-white');
                        item.querySelectorAll('.notification-status-dot').forEach((dot) => {
                            dot.classList.remove('bg-emerald-500');
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
                    item.classList.remove('border-emerald-200', 'bg-emerald-50/60');
                    item.classList.add('border-slate-200', 'bg-white');
                    item.querySelectorAll('.notification-status-dot').forEach((dot) => {
                        dot.classList.remove('bg-emerald-500');
                        dot.classList.add('bg-slate-200');
                    });
                });
            }
        });
    });
})();
