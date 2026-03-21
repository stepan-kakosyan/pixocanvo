(() => {
    function byId(id) {
        return document.getElementById(id);
    }

    function show(el) {
        if (el) {
            el.classList.remove('hidden');
        }
    }

    function hide(el) {
        if (el) {
            el.classList.add('hidden');
        }
    }

    function initializeCommunityModals(root) {
        const scope = root instanceof Element ? root : document;
        const modalBackdrop = byId('modal-backdrop');
        const invitationModal = byId('invitation-modal');
        const leaveModal = byId('leave-modal');
        const deleteModal = byId('delete-modal');
        const removeMemberModal = byId('remove-member-modal');

        const invitationInput = byId('invitation-link-input');
        const copyInviteButton = byId('copy-invite-link-btn');

        const leaveForm = byId('leave-community-form');
        const deleteForm = byId('delete-community-form');
        const removeMemberForm = byId('remove-member-form');
        const leaveModalText = byId('leave-modal-text');
        const deleteModalText = byId('delete-modal-text');
        const removeMemberModalText = byId('remove-member-modal-text');

        if (!modalBackdrop) {
            return;
        }

        if (!document.body.dataset.communityModalEscapeBound) {
            document.body.dataset.communityModalEscapeBound = 'true';
            document.addEventListener('keydown', (event) => {
                if (event.key === 'Escape') {
                    hide(modalBackdrop);
                    hide(invitationModal);
                    hide(leaveModal);
                    hide(deleteModal);
                    hide(removeMemberModal);
                }
            });
        }

        const hideAllModals = () => {
            hide(modalBackdrop);
            hide(invitationModal);
            hide(leaveModal);
            hide(deleteModal);
            hide(removeMemberModal);
        };

        const openModal = (modal) => {
            if (!modal) {
                return;
            }
            show(modalBackdrop);
            show(modal);
        };

        if (!modalBackdrop.dataset.communityModalBound) {
            modalBackdrop.dataset.communityModalBound = 'true';
            modalBackdrop.addEventListener('click', hideAllModals);
        }

        scope.querySelectorAll('.invitation-link-btn').forEach((btn) => {
            if (btn.dataset.communityModalBound) {
                return;
            }
            btn.dataset.communityModalBound = 'true';
            btn.addEventListener('click', () => {
                const url = String(btn.getAttribute('data-invite-url') || '');
                if (invitationInput) {
                    invitationInput.value = url;
                }
                openModal(invitationModal);
            });
        });

        if (copyInviteButton && invitationInput && !copyInviteButton.dataset.communityModalBound) {
            copyInviteButton.dataset.communityModalBound = 'true';
            copyInviteButton.addEventListener('click', async () => {
                const url = invitationInput.value;
                try {
                    if (navigator.clipboard && navigator.clipboard.writeText) {
                        await navigator.clipboard.writeText(url);
                    } else {
                        invitationInput.focus();
                        invitationInput.select();
                        document.execCommand('copy');
                    }
                    copyInviteButton.textContent = 'Copied!';
                    window.setTimeout(() => {
                        copyInviteButton.textContent = 'Copy URL';
                    }, 1200);
                } catch (_error) {
                    copyInviteButton.textContent = 'Copy failed';
                    window.setTimeout(() => {
                        copyInviteButton.textContent = 'Copy URL';
                    }, 1200);
                }
            });
        }

        scope.querySelectorAll('.leave-community-btn').forEach((btn) => {
            if (btn.dataset.communityModalBound) {
                return;
            }
            btn.dataset.communityModalBound = 'true';
            btn.addEventListener('click', () => {
                const name = String(btn.getAttribute('data-community-name') || '');
                const leaveUrl = String(btn.getAttribute('data-leave-url') || '');
                if (leaveForm) {
                    leaveForm.action = leaveUrl;
                }
                if (leaveModalText && name) {
                    leaveModalText.textContent = `Are you sure you want to leave "${name}"?`;
                }
                openModal(leaveModal);
            });
        });

        scope.querySelectorAll('.delete-community-btn').forEach((btn) => {
            if (btn.dataset.communityModalBound) {
                return;
            }
            btn.dataset.communityModalBound = 'true';
            btn.addEventListener('click', () => {
                const name = String(btn.getAttribute('data-community-name') || '');
                const deleteUrl = String(btn.getAttribute('data-delete-url') || '');
                if (deleteForm) {
                    deleteForm.action = deleteUrl;
                }
                if (deleteModalText && name) {
                    deleteModalText.textContent = `Delete "${name}" permanently? This action cannot be undone. All data will be deleted and cannot be restored.`;
                }
                openModal(deleteModal);
            });
        });

        scope.querySelectorAll('.remove-member-btn').forEach((btn) => {
            if (btn.dataset.communityModalBound) {
                return;
            }
            btn.dataset.communityModalBound = 'true';
            btn.addEventListener('click', () => {
                const memberName = String(btn.getAttribute('data-member-name') || '');
                const removeUrl = String(btn.getAttribute('data-remove-url') || '');
                if (removeMemberForm) {
                    removeMemberForm.action = removeUrl;
                }
                if (removeMemberModalText && memberName) {
                    removeMemberModalText.textContent =
                        `Are you sure you want to remove "${memberName}" from this community?`;
                }
                openModal(removeMemberModal);
            });
        });

        scope.querySelectorAll('.close-modal-btn').forEach((btn) => {
            if (btn.dataset.communityModalBound) {
                return;
            }
            btn.dataset.communityModalBound = 'true';
            btn.addEventListener('click', hideAllModals);
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        initializeCommunityModals(document);
    });

    document.body.addEventListener('htmx:load', (event) => {
        initializeCommunityModals(event.target);
    });
})();
